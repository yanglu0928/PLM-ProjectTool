"""Disposable PG18 proof of explicit Windows Evidence write composition.

All identity, key, License and document bytes are synthetic. No production
account, service, data root or customer file is modified.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import uuid
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.production_login import (
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app,
)
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.entrypoints.windows_evidence_list_cursor import ProductionEvidenceCursorStartupError
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.parser.application.structured_result import ParsedNode, ParsedResult, TextRangePosition
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("evd_pg_helpers", ROOT / "validation/evd-01-a03-p02-a02-p01/verify.py")
assert SPEC is not None and SPEC.loader is not None
HELPER = module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
CSRF = b"c" * 32


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


def seed_user(db, name: str, token: bytes) -> uuid.UUID:
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (name, name.lower()),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (user_id,),
    ).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,"
               "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
               (credential, user_id))
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id),
    )
    return user_id


def headers(token: bytes, key: str) -> dict[str, str]:
    return {"origin": "http://localhost", "cookie": "plm_session=" + token.hex(),
            "x-csrf-token": CSRF.hex(), "idempotency-key": key}


def verify(port: int, scratch: Path) -> None:
    url = URL.create("postgresql+psycopg", username=HELPER.USER, host="127.0.0.1",
                     port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    data_root = scratch / "data-root"
    data_root.mkdir()
    content = b"Synthetic fixed Evidence document."
    digest = hashlib.sha256(content).digest()
    pm_token, outsider_token = b"p" * 32, b"o" * 32
    with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                         dbname="postgres", autocommit=True) as db:
        pm = seed_user(db, "Evidence PM", pm_token)
        seed_user(db, "Evidence Outsider", outsider_token)
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('EVCP','evcp','Evidence composition',%s) RETURNING project_id", (pm,),
        ).fetchone()[0]
        department = db.execute(
            "INSERT INTO plm.prj_departments(project_id,department_code,"
            "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
            "RETURNING department_id", (project,),
        ).fetchone()[0]
        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                   "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, pm, department))
        document = db.execute(
            "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
            "original_display_name,created_by) VALUES "
            "('PROJECT',%s,'PROJECT_RECORD','Synthetic','synthetic.txt',%s) "
            "RETURNING document_id", (project, pm),
        ).fetchone()[0]
        file_id = uuid.uuid4()
        _, locator = LocalFileStorage.locators(
            scope="PROJECT", project_id=project, file_object_id=file_id,
        )
        path = data_root / locator
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
            "storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,"
            "detected_mime,available_at) VALUES "
            "(%s,'PROJECT',%s,'PERSISTENT',%s,'synthetic.txt',%s,'AVAILABLE',%s,%s,"
            "'text/plain',statement_timestamp())",
            (file_id, project, locator, pm, digest, len(content)),
        )
        version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
            "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
            "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document, project, file_id, digest, len(content), Jsonb({}), pm),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                   "WHERE document_id=%s", (version, version, document))
        position = TextRangePosition(0, len(content), digest.hex())
        parsed = ParsedResult(
            document_version_id=version, source_sha256=digest,
            parser_profile="PLAIN_TEXT", parser_version="1",
            nodes=(ParsedNode("text-line-1", "TEXT_LINE", content.decode("ascii"), position),),
        )
        job = db.execute(
            "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,"
            "trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
            "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,'evd-compose-parse',3) "
            "RETURNING job_id",
            (project, pm, str(uuid.uuid4()),
             Jsonb({"document_id": str(document), "document_version_id": str(version)})),
        ).fetchone()[0]
        parse_record = db.execute(
            "INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
            "parser_profile,parser_version,job_ref,attempt_no) VALUES "
            "(%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,1) RETURNING parse_record_id",
            (version, project, job),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                   "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s",
                   (parse_record,))
        result_id = uuid.uuid4()
        stored = LocalParseResultStorage(data_root).write_once(
            scope="PROJECT", project_id=project, result_ref_id=result_id,
            content=parsed.canonical_bytes(),
        )
        db.execute(
            "INSERT INTO plm.doc_parse_result_refs(parse_result_ref_id,parse_record_id,"
            "storage_locator,result_schema_version,sha256,size_bytes) VALUES (%s,%s,%s,1,%s,%s)",
            (result_id, parse_record, stored.storage_locator, stored.sha256, stored.size_bytes),
        )
        db.execute("UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                   "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                   "retryable=false,lock_version=2 WHERE parse_record_id=%s",
                   (result_id, stored.sha256, parse_record))
    guard = Guard()
    settings = BootstrapSettings(data_root=data_root, trusted_origins=("http://localhost",))
    cursor_patches = {
        "create_windows_secret_list_cursor_codec": SecretListCursorCodec(b"q" * 32),
        "create_windows_project_member_cursor_codec": MemberListCursorCodec(b"m" * 32),
        "create_windows_project_department_cursor_codec": DepartmentListCursorCodec(b"d" * 32),
        "create_windows_document_list_cursor_codec": DocumentListCursorCodec(b"l" * 32),
        "create_windows_document_version_cursor_codec": VersionListCursorCodec(b"v" * 32),
        "create_windows_document_parse_cursor_codec": ParseListCursorCodec(b"p" * 32),
        "create_windows_user_list_cursor_codec": UserListCursorCodec(b"u" * 32),
        "create_windows_job_list_cursor_codec": JobListCursorCodec(b"j" * 32),
        "create_windows_audit_cursor_codec": AuditListCursorCodec(b"a" * 32),
        "create_windows_evidence_list_cursor_codec": EvidenceListCursorCodec(b"e" * 32),
    }
    issuer = HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda _ref: b"u" * 32),
                                   key_ref="document-upload-token-v1")
    with ExitStack() as stack:
        stack.enter_context(patch("plm_assistant.entrypoints.production_login.read_database_url", return_value=url))
        stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                                  return_value=SimpleNamespace(guard=guard)))
        stack.enter_context(patch("plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                                  return_value=object()))
        stack.enter_context(patch("plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",
                                  return_value=issuer))
        for name, codec in cursor_patches.items():
            stack.enter_context(patch(f"plm_assistant.entrypoints.production_login.{name}",
                                      return_value=codec))
        login_only = create_production_login_app(settings)
        read_only = create_production_platform_app(settings)
        write = create_production_platform_write_app(settings)
        with patch("plm_assistant.entrypoints.production_login.create_windows_evidence_list_cursor_codec",
                   side_effect=ProductionEvidenceCursorStartupError()):
            missing_key = create_production_platform_app(settings)
        body = {"document_id": str(document), "document_version_id": str(version),
                "locator": {"locator_type": "DOCUMENT"}, "display_label": "Full document"}
        endpoint = f"/api/v1/projects/{project}/evidence"
        eligibility_body = {"eligibility_state": "ELIGIBLE",
                            "reason": "人工核对合成原始记录"}
        with TestClient(login_only, base_url="http://localhost") as client:
            assert client.post(endpoint, headers=headers(pm_token, "evd-login-closed-001"),
                               json=body).status_code == 404
            assert client.post(endpoint + "/" + str(uuid.uuid4()) + ":set-eligibility",
                               headers={**headers(pm_token, "evd-login-elig-001"),
                                        "if-match": '"v0"'},
                               json=eligibility_body).status_code == 404
            assert client.post(endpoint + "/" + str(uuid.uuid4()) + ":lookup-eligibility-operation",
                               headers=headers(pm_token, "evd-login-lookup-001"),
                               json={"operation_key": "evd-login-elig-001"}).status_code == 404
        with TestClient(read_only, base_url="http://localhost") as client:
            assert client.post(endpoint, headers=headers(pm_token, "evd-read-closed-001"),
                               json=body).status_code == 405
        with TestClient(missing_key, base_url="http://localhost") as client:
            assert client.get(endpoint, headers=headers(pm_token, "evd-missing-key-001")).status_code == 404
            assert client.get(f"/api/v1/projects/{project}/documents/{document}",
                              headers=headers(pm_token, "evd-missing-key-001")).status_code == 200
        with TestClient(write, base_url="http://localhost") as client:
            first = client.post(endpoint, headers=headers(pm_token, "evd-create-write-001"), json=body)
            replay = client.post(endpoint, headers=headers(pm_token, "evd-create-write-001"), json=body)
            assert first.status_code == replay.status_code == 201, (first.text, replay.text)
            assert first.json()["data"] == replay.json()["data"]
            assert first.json()["data"]["content_fingerprint"] == digest.hex()
            eligibility_path = endpoint + "/" + first.json()["data"]["evidence_id"] + ":set-eligibility"
            lookup_path = endpoint + "/" + first.json()["data"]["evidence_id"] + ":lookup-eligibility-operation"
            eligibility_headers = {**headers(pm_token, "evd-write-elig-001"),
                                   "if-match": '"v0"'}
            decided = client.post(eligibility_path, headers=eligibility_headers,
                                  json=eligibility_body)
            repeated = client.post(eligibility_path, headers=eligibility_headers,
                                   json=eligibility_body)
            assert decided.status_code == repeated.status_code == 200, (decided.text, repeated.text)
            assert decided.json()["data"] == repeated.json()["data"]
            assert decided.headers["etag"] == '"v1"'
            lookup_headers = {key: value for key, value in headers(pm_token, "evd-lookup-001").items()
                              if key != "idempotency-key"}
            completed = client.post(lookup_path, headers=lookup_headers,
                                    json={"operation_key": "evd-write-elig-001"})
            assert completed.status_code == 200, completed.text
            assert completed.json()["data"] == {"status": "COMPLETED",
                "evidence_id": first.json()["data"]["evidence_id"], "first_status_code": 200}
            unknown = client.post(lookup_path, headers=lookup_headers,
                                  json={"operation_key": "evd-lookup-missing-001"})
            assert unknown.status_code == 200 and unknown.json()["data"] == {"status": "UNCONFIRMED"}
            assert client.post(lookup_path, headers=headers(outsider_token, "evd-lookup-outside"),
                               json={"operation_key": "evd-write-elig-001"}).status_code == 404
            assert client.post(eligibility_path,
                               headers={**headers(outsider_token, "evd-write-elig-outsider"),
                                        "if-match": '"v1"'},
                               json=eligibility_body).status_code == 404
            viewer_path = endpoint + "/" + first.json()["data"]["evidence_id"] + "/viewer"
            viewer = client.get(viewer_path, headers=headers(pm_token, "evd-viewer-document-001"))
            assert viewer.status_code == 200, viewer.text
            assert viewer.json()["data"]["precision"] == "DOCUMENT"
            assert viewer.json()["data"]["document_version_id"] == str(version)
            content_url = viewer.json()["data"]["content_url"]
            assert client.get(content_url, headers=headers(pm_token, "evd-viewer-content-001")).content == content
            listed = client.get(endpoint + "?page_size=1", headers=headers(pm_token, "evd-read-001"))
            assert listed.status_code == 200, listed.text
            assert listed.json()["data"]["items"][0]["evidence_id"] == first.json()["data"]["evidence_id"]
            node_body = {**body, "locator": position.to_locator(),
                         "parse_record_id": str(parse_record),
                         "display_label": "Text line"}
            node = client.post(endpoint, headers=headers(pm_token, "evd-create-node-001"), json=node_body)
            assert node.status_code == 201, node.text
            assert node.json()["data"]["content_fingerprint"] == digest.hex()
            node_replay = client.post(endpoint, headers=headers(pm_token, "evd-create-node-001"), json=node_body)
            assert node_replay.status_code == 201 and node_replay.json()["data"] == node.json()["data"]
            node_viewer_path = endpoint + "/" + node.json()["data"]["evidence_id"] + "/viewer"
            node_viewer = client.get(node_viewer_path, headers=headers(pm_token, "evd-viewer-node-001"))
            assert node_viewer.status_code == 200, node_viewer.text
            assert node_viewer.json()["data"]["precision"] == "PARSED_NODE"
            assert node_viewer.json()["data"]["locator"] == position.to_locator()
            assert client.get(node_viewer_path, headers=headers(outsider_token,
                                                                "evd-viewer-outsider-001")).status_code == 404
            outsider = client.post(endpoint, headers=headers(outsider_token, "evd-outsider-001"), json=body)
            assert outsider.status_code == 404, outsider.text
            guard.enabled = False
            assert client.post(lookup_path, headers=lookup_headers,
                               json={"operation_key": "evd-write-elig-001"}).status_code == 403
            denied = client.post(endpoint, headers=headers(pm_token, "evd-license-deny-001"), json=body)
            assert denied.status_code == 403, denied.text
            assert client.get(viewer_path, headers=headers(pm_token,
                                                           "evd-viewer-license-001")).status_code == 403
            guard.enabled = True
            with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                                 dbname="postgres", autocommit=True) as db:
                db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' "
                           "WHERE project_id=%s AND user_id=%s", (project, pm))
            demoted = client.post(endpoint, headers=headers(pm_token, "evd-create-write-001"), json=body)
            assert demoted.status_code == 404, demoted.text
            assert client.post(eligibility_path, headers=eligibility_headers,
                               json=eligibility_body).status_code == 404
            assert client.post(lookup_path, headers=lookup_headers,
                               json={"operation_key": "evd-write-elig-001"}).status_code == 404
        with TestClient(read_only, base_url="http://localhost") as client:
            detail = client.get(endpoint + "/" + first.json()["data"]["evidence_id"],
                                headers=headers(pm_token, "evd-read-002"))
            assert detail.status_code == 200, detail.text  # Customer member retains read rights.
            read_only_decision = client.post(eligibility_path, headers=eligibility_headers,
                                             json=eligibility_body)
            assert read_only_decision.status_code == 405, read_only_decision.status_code
            read_only_lookup = client.post(lookup_path, headers=lookup_headers,
                                           json={"operation_key": "evd-write-elig-001"})
            assert read_only_lookup.status_code in (404, 405), read_only_lookup.status_code
            assert client.get(node_viewer_path, headers=headers(pm_token,
                                                                "evd-viewer-demoted-001")).status_code == 200
            path.write_bytes(content[:-1] + b"!")
            assert client.get(viewer_path, headers=headers(pm_token,
                                                           "evd-viewer-tamper-001")).status_code == 409
            path.write_bytes(content)
            result_path = data_root / stored.storage_locator
            result_bytes = result_path.read_bytes()
            result_path.write_bytes(result_bytes[:-1] + b"!")
            assert client.get(node_viewer_path, headers=headers(pm_token,
                                                                "evd-viewer-result-tamper-001")).status_code == 409
            result_path.write_bytes(result_bytes)
        with TestClient(missing_key, base_url="http://localhost") as client:
            assert client.get(viewer_path, headers=headers(pm_token,
                                                           "evd-viewer-no-cursor-001")).status_code == 200
        with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.doc_documents SET effective_version_ref=NULL WHERE document_id=%s",
                       (document,))
            db.execute("UPDATE plm.doc_document_versions SET availability_state='REVOKED' "
                       "WHERE document_version_id=%s", (version,))
        with TestClient(read_only, base_url="http://localhost") as client:
            revoked = client.get(viewer_path, headers=headers(pm_token,
                                                              "evd-viewer-revoked-001"))
            assert revoked.status_code == 404, (revoked.status_code, revoked.text)
            assert client.get(endpoint + "/" + first.json()["data"]["evidence_id"],
                              headers=headers(pm_token, "evd-read-revoked-001")).status_code == 200
    with psycopg.connect(host="127.0.0.1", port=port, user=HELPER.USER,
                         dbname="postgres") as db:
        evidence_id = uuid.UUID(first.json()["data"]["evidence_id"])
        assert db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM plm.evd_evidence_records WHERE evidence_id=%s",
                          (evidence_id,)).fetchone()[0] == 1
        assert db.execute("SELECT source_parse_record_id FROM plm.evd_evidence_records "
                          "WHERE evidence_id=%s", (evidence_id,)).fetchone()[0] is None
        assert db.execute("SELECT source_parse_record_id FROM plm.evd_evidence_records "
                          "WHERE evidence_id=%s", (uuid.UUID(node.json()["data"]["evidence_id"]),)
                          ).fetchone()[0] == parse_record
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                          "AND action='EVIDENCE_CREATED'", (evidence_id,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                          "AND action='EVIDENCE_ELIGIBILITY_SET'", (evidence_id,)).fetchone()[0] == 1
    print("PASS: isolated PG18 Windows Evidence create/read/Viewer/eligibility/receipt lookup, fixed source, content URL, tamper/revocation/role/License isolation")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-evd-compose-pg-"))
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
        verify(port, scratch)
    finally:
        if started:
            HELPER.run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(bin_dir / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) and scratch.name.startswith("plm-evd-compose-pg-"):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
