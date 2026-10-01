"""Disposable PG18 proof of human Evidence eligibility with synthetic records only."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.application.eligibility_access import EvidenceEligibilityAccess
from plm_assistant.modules.evidence.application.lookup_eligibility_operation import (
    EvidenceEligibilityLookupError, EvidenceEligibilityOperationLookupService,
    LookupEvidenceEligibilityOperation,
)
from plm_assistant.modules.evidence.api.set_eligibility import create_evidence_eligibility_router
from plm_assistant.modules.evidence.api.lookup_eligibility_operation import (
    create_evidence_eligibility_operation_lookup_router,
)
from plm_assistant.modules.evidence.application.set_eligibility import (
    EvidenceEligibilityCommandError, EvidenceEligibilityService, SetEvidenceEligibility,
)
from plm_assistant.modules.evidence.infrastructure.eligibility_repository import SqlAlchemyEvidenceEligibilityRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("evd_pg_helpers", ROOT / "validation/evd-01-a03-p02-a02-p01/verify.py")
assert SPEC is not None and SPEC.loader is not None
HELPER = module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
            raise RuntimeLicenseError("EXPIRED")
        return object()


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")


class Sessions:
    def __init__(self, actor):
        self.actor = actor

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.actor})()


def expect(code, action):
    try:
        action()
    except EvidenceEligibilityCommandError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError(f"expected {code}")


def expect_lookup(code, action):
    try:
        action()
    except EvidenceEligibilityLookupError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError(f"expected lookup {code}")


def insert_user(db, token, csrf):
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES ('Evidence Reviewer','evidence reviewer') RETURNING user_id",
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
        "state='ENABLED' WHERE user_id=%s", (credential, actor),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
    )
    return actor


def insert_source(db, *, actor, project, category, label):
    source = ("synthetic " + label).encode("ascii")
    sha = hashlib.sha256(source).digest()
    document = db.execute(
        "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
        "original_display_name,created_by) VALUES ('PROJECT',%s,%s,%s,%s,%s) "
        "RETURNING document_id", (project, category, label, label + ".txt", actor),
    ).fetchone()[0]
    file_id = db.execute(
        "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,"
        "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
        "VALUES ('PROJECT',%s,'PERSISTENT',%s,%s,%s,'AVAILABLE',%s,%s,'text/plain',"
        "statement_timestamp()) RETURNING file_object_id",
        (project, "synthetic/" + label, label + ".txt", actor, sha, len(source)),
    ).fetchone()[0]
    version = db.execute(
        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
        "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
        "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
        "RETURNING document_version_id",
        (document, project, file_id, sha, len(source), Jsonb({}), actor),
    ).fetchone()[0]
    evidence = db.execute(
        "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,document_version_id,"
        "locator_type,locator_payload,content_fingerprint,display_label,created_by) "
        "VALUES ('PROJECT',%s,%s,%s,'DOCUMENT',%s,%s,%s,%s) RETURNING evidence_id",
        (project, document, version, Jsonb({"locator_type": "DOCUMENT"}), sha,
         label, actor),
    ).fetchone()[0]
    return document, version, evidence


def verify(port):
    url = URL.create("postgresql+psycopg", username=HELPER.USER,
                     host="127.0.0.1", port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    token, csrf = b"s" * 32, b"c" * 32
    with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                         dbname="postgres", autocommit=True) as db:
        actor = insert_user(db, token, csrf)
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('ELIG1','elig1','Synthetic Eligibility',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        dept = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
            "RETURNING department_id", (project,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
            "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, actor, dept),
        )
        actual_doc, actual_version, actual = insert_source(
            db, actor=actor, project=project, category="PROJECT_RECORD", label="actual")
        _, _, template = insert_source(
            db, actor=actor, project=project, category="TEMPLATE", label="template")
        _, _, audit_case = insert_source(
            db, actor=actor, project=project, category="PROJECT_RECORD", label="auditcase")
        _, _, http_case = insert_source(
            db, actor=actor, project=project, category="PROJECT_RECORD", label="httpcase")
        _, revoked_version, revoked_case = insert_source(
            db, actor=actor, project=project, category="PROJECT_RECORD", label="revoked")
        _, _, concurrent_case = insert_source(
            db, actor=actor, project=project, category="PROJECT_RECORD", label="concurrent")
        foreign_project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('ELIG2','elig2','Foreign Synthetic',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        _, _, foreign_case = insert_source(
            db, actor=actor, project=foreign_project,
            category="PROJECT_RECORD", label="foreign")
    runtime = create_database_runtime(url)
    try:
        guard = Guard()
        source = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        access = EvidenceEligibilityAccess(
            session_token=token, csrf_token=csrf,
            session_access=SqlAlchemyProjectWriteAccess(),
            admin_access=SqlAlchemyLicenseImportAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
        )
        common = dict(
            unit_of_work=runtime.unit_of_work, access=access, source_facts=source,
            repository=SqlAlchemyEvidenceEligibilityRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), license_guard=guard,
        )
        service = EvidenceEligibilityService(
            **common, audit=AuditService(SqlAlchemyAuditRepository()))
        lookups = EvidenceEligibilityOperationLookupService(
            unit_of_work=runtime.unit_of_work, access=access,
            evidence=common["repository"], receipts=common["receipts"],
            license_guard=guard,
        )

        def lookup(evidence, key, project_id=project):
            return lookups.lookup(LookupEvidenceEligibilityOperation(
                actor, token, csrf, uuid.uuid4(), "PROJECT", project_id,
                evidence, key,
            ))

        def request(evidence, state="ELIGIBLE", reason="人工核对原始调研记录"):
            return SetEvidenceEligibility(
                actor, token, csrf, uuid.uuid4(), "PROJECT", project,
                evidence, 0, state, reason,
            )

        item = request(actual)
        first = service.set(item, idempotency_key="eligibility-pg-0001")
        assert first.etag == '"v1"' and first.eligibility_state == "ELIGIBLE"
        completed = lookup(actual, "eligibility-pg-0001")
        assert completed.status == "COMPLETED" and completed.evidence_id == actual
        assert completed.first_status_code == 200
        assert lookup(actual, "eligibility-pg-missing").status == "UNCONFIRMED"
        expect_lookup("CONFLICT_IDEMPOTENCY", lambda: lookup(
            template, "eligibility-pg-0001"))
        expect_lookup("RESOURCE_NOT_FOUND", lambda: lookup(
            foreign_case, "eligibility-pg-0001"))
        assert service.set(item, idempotency_key="eligibility-pg-0001") == first
        expect("CONFLICT_VERSION", lambda: service.set(
            item, idempotency_key="eligibility-pg-0002"))
        expect("CONFLICT_STATE", lambda: service.set(
            request(template), idempotency_key="eligibility-pg-0003"))
        expect("RESOURCE_NOT_FOUND", lambda: service.set(
            request(foreign_case), idempotency_key="eligibility-pg-foreign"))
        guard.enabled = False
        expect_lookup("LICENSE_OPERATION_DENIED", lambda: lookup(
            actual, "eligibility-pg-0001"))
        expect("LICENSE_OPERATION_DENIED", lambda: service.set(
            request(revoked_case), idempotency_key="eligibility-pg-license"))
        guard.enabled = True
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
        assert lookup(actual, "eligibility-pg-0001").status == "COMPLETED"
        expect("PROJECT_ARCHIVED", lambda: service.set(
            request(revoked_case), idempotency_key="eligibility-pg-archived"))
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s", (project,))
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                             dbname="postgres", autocommit=True) as db:
            db.execute(
                "UPDATE plm.doc_document_versions SET availability_state='REVOKED' "
                "WHERE document_version_id=%s", (revoked_version,),
            )
        expect("RESOURCE_NOT_FOUND", lambda: service.set(
            request(revoked_case), idempotency_key="eligibility-pg-revoked"))
        rejected = service.set(request(template, "INELIGIBLE", "仅为结构模板"),
                               idempotency_key="eligibility-pg-0004")
        assert rejected.etag == '"v1"'
        bad = EvidenceEligibilityService(**common, audit=FailingAudit())
        try:
            bad.set(request(audit_case), idempotency_key="eligibility-pg-0005")
        except RuntimeError as error:
            assert str(error) == "synthetic audit failure"
        else:
            raise AssertionError("Audit failure committed")
        router = create_evidence_eligibility_router(
            sessions=Sessions(actor),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=lambda _token, _csrf: service,
        )
        lookup_router = create_evidence_eligibility_operation_lookup_router(
            sessions=Sessions(actor),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=lambda _token, _csrf: lookups,
        )
        headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + token.hex(),
            "x-csrf-token": csrf.hex(),
            "idempotency-key": "eligibility-http-0001",
            "if-match": '"v0"',
        }
        path = f"/api/v1/projects/{project}/evidence/{http_case}:set-eligibility"
        body = {"eligibility_state": "ELIGIBLE", "reason": "人工核对合成记录"}
        with TestClient(create_app(evidence_eligibility_router=router,
                                   evidence_eligibility_operation_lookup_router=lookup_router),
                        base_url="https://plm.example.test") as client:
            posted = client.post(path, headers=headers, json=body)
            replayed = client.post(path, headers=headers, json=body)
            assert posted.status_code == replayed.status_code == 200, (posted.text, replayed.text)
            assert posted.json()["data"] == replayed.json()["data"]
            assert posted.headers["etag"] == '"v1"'
            assert client.post(path, headers={k: v for k, v in headers.items()
                                              if k != "x-csrf-token"},
                               json=body).status_code == 403
            lookup_path = (f"/api/v1/projects/{project}/evidence/"
                           f"{http_case}:lookup-eligibility-operation")
            lookup_headers = {key: value for key, value in headers.items()
                              if key not in ("idempotency-key", "if-match")}
            completed_http = client.post(
                lookup_path, headers=lookup_headers,
                json={"operation_key": "eligibility-http-0001"},
            )
            assert completed_http.status_code == 200, completed_http.text
            assert completed_http.json()["data"] == {
                "status": "COMPLETED", "evidence_id": str(http_case),
                "first_status_code": 200,
            }
            unknown_http = client.post(
                lookup_path, headers=lookup_headers,
                json={"operation_key": "eligibility-http-missing"},
            )
            assert unknown_http.status_code == 200, unknown_http.text
            assert unknown_http.json()["data"] == {"status": "UNCONFIRMED"}

        barrier = Barrier(2)

        class ConcurrentAccess:
            def require_in_transaction(self, *_args, **_kwargs):
                barrier.wait(timeout=10)

        concurrent = EvidenceEligibilityService(
            **{**common, "access": ConcurrentAccess()},
            audit=AuditService(SqlAlchemyAuditRepository()),
        )

        def race(index):
            try:
                result = concurrent.set(
                    request(concurrent_case, reason=f"合成并发复核 {index}"),
                    idempotency_key=f"eligibility-race-{index:04d}",
                )
                return ("SUCCESS", result.etag)
            except EvidenceEligibilityCommandError as error:
                return (error.code, None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(race, (1, 2)))
        assert sorted(code for code, _ in outcomes) == ["CONFLICT_VERSION", "SUCCESS"], outcomes
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                             dbname="postgres", autocommit=True) as db:
            assert db.execute(
                "SELECT eligibility_state,lock_version FROM plm.evd_evidence_records "
                "WHERE evidence_id=%s", (audit_case,),
            ).fetchone() == ("CANDIDATE", 0)
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='EVIDENCE_ELIGIBILITY_SET'",
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_EVIDENCE_SET_ELIGIBILITY'",
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT eligibility_state,lock_version FROM plm.evd_evidence_records "
                "WHERE evidence_id=%s", (concurrent_case,),
            ).fetchone() == ("ELIGIBLE", 1)
            db.execute(
                "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                "WHERE project_id=%s AND user_id=%s", (project, actor),
            )
        expect("RESOURCE_NOT_FOUND", lambda: service.set(
            item, idempotency_key="eligibility-pg-0001"))
        expect_lookup("RESOURCE_NOT_FOUND", lambda: lookup(actual, "eligibility-pg-0001"))
        print("PASS: isolated PG18 source/eligibility/HTTP replay, read-only receipt lookup, single concurrent winner, template/cross-project/revoked/License denial, Audit rollback, role revoke")
    finally:
        runtime.dispose()


def main():
    scratch = Path(tempfile.mkdtemp(prefix="plm-evd-elig-pg-"))
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
    port, started = HELPER.free_port(), False
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
            raise RuntimeError(f"PostgreSQL remains running; data retained at {scratch}")
        if scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) and scratch.name.startswith("plm-evd-elig-pg-"):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
