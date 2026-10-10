"""Isolated PG18 candidate create/replay/Audit/rollback with synthetic records."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.application.read_documents import DocumentVersionView
from plm_assistant.modules.evidence.application.create_evidence import CreateEvidence, EvidenceCreateService
from plm_assistant.modules.evidence.application.create_access import EvidenceCreateAccessError
from plm_assistant.modules.evidence.application.document_source_proof import EvidenceDocumentProof
from plm_assistant.modules.evidence.api.create_evidence import create_evidence_create_router
from plm_assistant.modules.evidence.infrastructure.create_repository import SqlAlchemyEvidenceCreateRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("evd_pg_helpers", ROOT / "validation/evd-01-a03-p02-a02-p01/verify.py")
assert SPEC is not None and SPEC.loader is not None
HELPER = module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class Access:
    allowed = True

    def require_in_transaction(self, *_args, **_kwargs):
        if not self.allowed:
            raise EvidenceCreateAccessError("RESOURCE_NOT_FOUND")


class Versions:
    def __init__(self, source_sha):
        self.source_sha = source_sha

    def get_version_for_trace(self, _tx, _query, document_id, document_version_id):
        from datetime import datetime, timezone
        return DocumentVersionView(document_version_id, document_id, 1,
                                   self.source_sha.hex(), 8, "text/plain", "AVAILABLE",
                                   None, datetime.now(timezone.utc), None)


class Proof:
    def __init__(self, source_sha):
        self.source_sha = source_sha

    def prove(self, _query, *, document_id, document_version_id, locator):
        return EvidenceDocumentProof(document_version_id, locator, self.source_sha)


class NoNodes:
    def prove(self, *_args, **_kwargs):
        raise AssertionError("DOCUMENT cannot use Parser node proof")


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("audit failure")


class Sessions:
    def __init__(self, actor):
        self.actor = actor

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.actor})()


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username=HELPER.USER, host="127.0.0.1",
                     port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    source = b"synthetic"
    digest = hashlib.sha256(source).digest()
    with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                           "VALUES ('Evidence Creator','evidence creator') RETURNING user_id").fetchone()[0]
        project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                             "VALUES ('EVDC','evdc','Evidence create',%s) RETURNING project_id", (actor,)).fetchone()[0]
        document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                              "original_display_name,created_by) VALUES "
                              "('PROJECT',%s,'PROJECT_RECORD','Synthetic','synthetic.txt',%s) "
                              "RETURNING document_id", (project, actor)).fetchone()[0]
        file_id = db.execute("INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,"
                             "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
                             "VALUES ('PROJECT',%s,'PERSISTENT','synthetic/only','synthetic.txt',%s,"
                             "'AVAILABLE',%s,%s,'text/plain',statement_timestamp()) RETURNING file_object_id",
                             (project, actor, digest, len(source))).fetchone()[0]
        version = db.execute("INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
                             "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
                             "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
                             "RETURNING document_version_id",
                             (document, project, file_id, digest, len(source), Jsonb({}), actor)).fetchone()[0]
    runtime = create_database_runtime(url)
    try:
        access = Access()
        common = dict(unit_of_work=runtime.unit_of_work, access=access, versions=Versions(digest),
                      document_proof=Proof(digest), node_proof=NoNodes(),
                      repository=SqlAlchemyEvidenceCreateRepository(),
                      receipts=SqlAlchemyIdempotencyReceipts())
        service = EvidenceCreateService(**common, audit=AuditService(SqlAlchemyAuditRepository()))
        command_value = CreateEvidence(actor, b"s" * 32, b"c" * 32, uuid.uuid4(),
                                       "PROJECT", project, document, version,
                                       {"locator_type": "DOCUMENT"}, "全文")
        key = "evidence-create-pg-001"
        first = service.create(command_value, idempotency_key=key)
        replay = service.create(command_value, idempotency_key=key)
        assert first == replay and first.eligibility_state == "CANDIDATE"
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER, dbname="postgres") as db:
            assert db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='EVIDENCE_CREATED'").fetchone()[0] == 1
        access.allowed = False
        try:
            service.create(command_value, idempotency_key=key)
        except EvidenceCreateAccessError as error:
            assert error.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("revoked replay accepted")
        access.allowed = True
        bad_service = EvidenceCreateService(**common, audit=FailingAudit())
        try:
            bad_service.create(command_value, idempotency_key="evidence-create-pg-002")
        except RuntimeError as error:
            assert str(error) == "audit failure"
        else:
            raise AssertionError("failed Audit committed Evidence")
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER, dbname="postgres") as db:
            assert db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                              "WHERE operation='V1_EVIDENCE_CREATE'").fetchone()[0] == 1
        router = create_evidence_create_router(
            sessions=Sessions(actor), origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=lambda _token, _csrf: service,
        )
        headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "evidence-create-http-001",
        }
        body = {"document_id": str(document), "document_version_id": str(version),
                "locator": {"locator_type": "DOCUMENT"}, "display_label": "Full document"}
        path = f"/api/v1/projects/{project}/evidence"
        with TestClient(create_app(evidence_create_router=router),
                        base_url="https://plm.example.test") as client:
            posted = client.post(path, headers=headers, json=body)
            retried = client.post(path, headers=headers, json=body)
            assert posted.status_code == retried.status_code == 201
            assert posted.json()["data"] == retried.json()["data"]
            access.allowed = False
            assert client.post(path, headers=headers, json=body).status_code == 404
            access.allowed = True
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER, dbname="postgres") as db:
            assert db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='EVIDENCE_CREATED'").fetchone()[0] == 2
    finally:
        runtime.dispose()
    print("PASS: isolated PG18 internal+HTTP Evidence 201 replay, single Audit per create, revoked replay denied, Audit rollback")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-evd-create-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(HELPER.PG_SOURCE / name, install / name)
    shutil.copy2(HELPER.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(HELPER.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (HELPER.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    bin_dir, data, log = install / "bin", scratch / "data", scratch / "postgres.log"
    port = HELPER.free_port()
    started = False
    try:
        HELPER.run(str(bin_dir / "initdb.exe"), "-D", str(data), "-U", HELPER.USER,
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        HELPER.run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            HELPER.run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(bin_dir / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) and scratch.name.startswith("plm-evd-create-pg-"):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
