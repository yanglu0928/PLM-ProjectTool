"""Isolated PG18 Evidence metadata authorization and stable keyset proof."""

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

from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.evidence.api.read_evidence import create_evidence_read_router
from plm_assistant.modules.evidence.application.read_evidence import EvidenceReadError, EvidenceReadQuery, EvidenceReadService
from plm_assistant.modules.evidence.infrastructure.read_repository import SqlAlchemyEvidenceReadRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
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


class Sessions:
    def validate(self, token):
        if token not in (b"p" * 32, b"o" * 32, b"a" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers(token: bytes) -> dict[str, str]:
    return {"cookie": "plm_session=" + token.hex()}


def user(db, name: str, token: bytes, *, admin: bool = False):
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id",
        (name, name.lower(), "DEPLOYMENT_ADMIN" if admin else "NONE"),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,"
               "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
               (credential, actor))
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(b"c" * 32).digest(), actor),
    )
    return actor


def project_document(db, project, actor, code: str):
    doc = db.execute(
        "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
        "original_display_name,created_by) VALUES "
        "('PROJECT',%s,'PROJECT_RECORD',%s,'synthetic.txt',%s) RETURNING document_id",
        (project, code, actor),
    ).fetchone()[0]
    content = code.encode("ascii")
    digest = hashlib.sha256(content).digest()
    file_id = db.execute(
        "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,"
        "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
        "VALUES ('PROJECT',%s,'PERSISTENT',%s,'synthetic.txt',%s,'AVAILABLE',%s,%s,"
        "'text/plain',statement_timestamp()) RETURNING file_object_id",
        (project, f"synthetic/{code}", actor, digest, len(content)),
    ).fetchone()[0]
    version = db.execute(
        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
        "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
        "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) RETURNING document_version_id",
        (doc, project, file_id, digest, len(content), Jsonb({}), actor),
    ).fetchone()[0]
    return doc, version, digest


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username=HELPER.USER, host="127.0.0.1",
                     port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    pm_token, outsider_token, admin_token = b"p" * 32, b"o" * 32, b"a" * 32
    with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                         dbname="postgres", autocommit=True) as db:
        pm = user(db, "Evidence Read PM", pm_token)
        outsider = user(db, "Evidence Read Outside", outsider_token)
        admin = user(db, "Evidence Read Admin", admin_token, admin=True)
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('ER1','er1','Evidence read one',%s) RETURNING project_id", (pm,),
        ).fetchone()[0]
        other = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('ER2','er2','Evidence read two',%s) RETURNING project_id", (outsider,),
        ).fetchone()[0]
        department = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
            "RETURNING department_id", (project,),
        ).fetchone()[0]
        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                   "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, pm, department))
        doc, version, digest = project_document(db, project, pm, "Alpha")
        other_doc, other_version, other_digest = project_document(db, other, outsider, "Beta")
        ids = []
        for index in range(3):
            ids.append(db.execute(
                "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
                "document_version_id,locator_type,locator_payload,content_fingerprint,"
                "display_label,created_by,created_at) VALUES "
                "('PROJECT',%s,%s,%s,'DOCUMENT',%s,%s,%s,%s,"
                "'2026-10-01T00:00:00+00:00') RETURNING evidence_id",
                (project, doc, version, Jsonb({"locator_type": "DOCUMENT"}), digest,
                 f"Evidence {index}", pm),
            ).fetchone()[0])
        foreign = db.execute(
            "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
            "document_version_id,locator_type,locator_payload,content_fingerprint,"
            "display_label,created_by) VALUES "
            "('PROJECT',%s,%s,%s,'DOCUMENT',%s,%s,'Foreign',%s) RETURNING evidence_id",
            (other, other_doc, other_version, Jsonb({"locator_type": "DOCUMENT"}),
             other_digest, outsider),
        ).fetchone()[0]
    runtime = create_database_runtime(url)
    guard = Guard()
    try:
        service = EvidenceReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyEvidenceReadRepository(),
        )
        query = EvidenceReadQuery(pm_token, uuid.uuid4(), "PROJECT", project)
        seen = []
        after = None
        for _ in range(3):
            page = service.list(query, after=after, limit=1)
            assert len(page.items) == 1
            seen.append(page.items[0].evidence_id)
            after = page.next_after
        assert set(seen) == set(ids) and len(seen) == 3
        assert after is None
        assert service.get(query, ids[0]).evidence_id == ids[0]
        try:
            service.get(query, foreign)
        except EvidenceReadError as error:
            assert error.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("cross-project Evidence visible")
        wrong = EvidenceReadQuery(outsider_token, uuid.uuid4(), "PROJECT", project)
        try:
            service.list(wrong)
        except EvidenceReadError as error:
            assert error.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("nonmember read Evidence")
        global_query = EvidenceReadQuery(admin_token, uuid.uuid4(), "GLOBAL", None)
        assert service.list(global_query).items == ()
        guard.enabled = False
        try:
            service.list(query)
        except EvidenceReadError as error:
            assert error.code == "LICENSE_OPERATION_DENIED"
        else:
            raise AssertionError("expired License read Evidence")
        guard.enabled = True
        router = create_evidence_read_router(
            sessions=Sessions(), evidence=service,
            origins=LoginOriginPolicy(["http://localhost"]),
            cursors=EvidenceListCursorCodec(b"e" * 32),
        )
        path = f"/api/v1/projects/{project}/evidence"
        with TestClient(create_app(evidence_read_router=router),
                        base_url="http://localhost") as client:
            first = client.get(path + "?page_size=1", headers=headers(pm_token))
            assert first.status_code == 200, first.text
            cursor = first.json()["data"]["next_cursor"]
            assert cursor
            second = client.get(path + "?page_size=1&cursor=" + cursor,
                                headers=headers(pm_token))
            assert second.status_code == 200, second.text
            assert second.json()["data"]["items"][0]["evidence_id"] != first.json()["data"]["items"][0]["evidence_id"]
            detail = client.get(path + "/" + str(ids[0]), headers=headers(pm_token))
            assert detail.status_code == 200 and "display_excerpt" not in detail.json()["data"]
            assert client.get(path, headers=headers(outsider_token)).status_code == 404
            assert client.get("/api/v1/global/evidence", headers=headers(admin_token)).status_code == 200
            guard.enabled = False
            assert client.get(path, headers=headers(pm_token)).status_code == 403
    finally:
        runtime.dispose()
    print("PASS: isolated PG18 Evidence metadata internal+HTTP keyset, Session/project isolation, admin and License")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-evd-read-pg-"))
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
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) and scratch.name.startswith("plm-evd-read-pg-"):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
