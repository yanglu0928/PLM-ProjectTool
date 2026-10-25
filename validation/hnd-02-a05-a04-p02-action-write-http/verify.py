"""Win11/PostgreSQL 18 HTTP proof for the Windows Action write composition."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_handover_action import (
    create_windows_handover_action_write_routers,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://plm.example.test"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_action_http_fixture")
connect, seed_user, CSRF, Guard = p01.connect, p01.seed_user, p01.CSRF, p01.Guard


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        assert type(token) is bytes and len(token) == 32
        assert csrf_token == CSRF and require_csrf is True
        return object()


def headers(token: bytes, version: int, *, key: str | None = None) -> dict[str, str]:
    return {
        "origin": ORIGIN,
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": CSRF.hex(),
        "if-match": f'"v{version}"',
        "idempotency-key": key or str(uuid.uuid4()),
    }


def main() -> None:
    name = "hnd02a05a04p02_" + uuid.uuid4().hex[:8]
    pm_token, owner_token = b"p" * 32, b"o" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "HTTP Action PM", "NONE", pm_token)
                    owner = seed_user(db, "HTTP Action Owner", "NONE", owner_token)
                    project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDHTTP','hndhttp','Action HTTP',%s) RETURNING project_id",
                        (pm,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,"
                        "department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') "
                        "RETURNING department_id", (project,),
                    ).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"),
                                       (owner, "IMPLEMENTATION_MEMBER")):
                        db.execute(
                            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                            "project_role) VALUES (%s,%s,%s,%s)",
                            (project, user, department, role),
                        )
                    source = p01.seed_project_document(db, pm, project, "http-response")
                    submission_evidence, verification_evidence = uuid.uuid4(), uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for evidence_id, label in (
                                (submission_evidence, "Submission"),
                                (verification_evidence, "Verification")):
                            db.execute(
                                "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,"
                                "document_id,document_version_id,locator_type,locator_schema_version,"
                                "locator_payload,content_fingerprint,display_label,eligibility_state,"
                                "eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,"
                                "'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,%s,"
                                "'ELIGIBLE','fixture',%s)",
                                (evidence_id, project, source.document_id,
                                 source.document_version_id, b"e" * 32, label, pm),
                            )

                routers = create_windows_handover_action_write_routers(
                    runtime, sessions=Sessions(),
                    origins=LoginOriginPolicy([ORIGIN]), license_guard=Guard(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )
                app = create_app(
                    handover_action_command_router=routers.commands,
                    handover_action_lifecycle_router=routers.lifecycle,
                )
                root = f"/api/v1/projects/{project}/handover-action-items"
                due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace(
                    "+00:00", "Z",
                )
                body = {
                    "source_analysis_version_ref": None, "source_item_id": None,
                    "human_source_reason": "Face-to-face project meeting",
                    "action_type": "PROVIDE_INFO", "title": "Provide signed response",
                    "requested_input_spec": {"fields": [{
                        "name": "response", "format": "document",
                        "example": "Signed response", "required": True,
                    }]},
                    "owner_ref": str(owner), "due_at": due, "priority": "HIGH",
                    "created_reason": "Project manager registered customer follow-up",
                }
                with TestClient(app, base_url=ORIGIN) as client:
                    created = client.post(root, headers=headers(pm_token, 0), json=body)
                    assert created.status_code == 201, created.text
                    action = created.json()["data"]["action_item_id"]
                    path = root + "/" + action
                    patched = client.patch(
                        path, headers=headers(pm_token, 0),
                        json={"priority": "URGENT", "title": "Provide final signed response"},
                    )
                    assert patched.status_code == 200 and patched.headers["etag"] == '"v1"', patched.text
                    started = client.post(
                        path + ":start", headers=headers(owner_token, 1),
                        json={"reason": "Response preparation started"},
                    )
                    assert started.status_code == 200 and started.json()["data"]["action_state"] == "IN_PROGRESS", started.text
                    submitted = client.post(
                        path + ":submit", headers=headers(owner_token, 2), json={
                            "response_documents": [{
                                "document_id": str(source.document_id),
                                "document_version_id": str(source.document_version_id),
                            }],
                            "evidence_refs": [str(submission_evidence)],
                            "reason": "Signed response submitted",
                        },
                    )
                    assert submitted.status_code == 200 and submitted.json()["data"]["action_state"] == "SUBMITTED", submitted.text
                    verified = client.post(
                        path + ":verify", headers=headers(pm_token, 3), json={
                            "evidence_refs": [str(verification_evidence)],
                            "reason": "Response and evidence verified",
                        },
                    )
                    assert verified.status_code == 200 and verified.json()["data"]["action_state"] == "VERIFIED", verified.text

                    trace_link = uuid.uuid4()
                    with connect(name) as db:
                        db.execute(
                            "INSERT INTO plm.trc_links(trace_link_id,scope,project_id,"
                            "source_owner_module,source_object_type,source_object_id,source_version_id,"
                            "source_project_id,target_owner_module,target_object_type,target_object_id,"
                            "target_version_id,target_project_id,relation_type,created_by,trace_id) "
                            "VALUES (%s,'PROJECT',%s,'handover','HND-02',%s,%s,%s,'survey',"
                            "'SRV-02',%s,%s,%s,'REFINES',%s,%s)",
                            (trace_link, project, uuid.uuid4(), uuid.uuid4(), project,
                             uuid.uuid4(), uuid.uuid4(), project, pm, uuid.uuid4()),
                        )
                    closed = client.post(
                        path + ":close", headers=headers(pm_token, 4), json={
                            "resolution_trace_ref": str(trace_link),
                            "reason": "Attempt close before downstream Owner exists",
                        },
                    )
                    assert closed.status_code == 422, closed.text
                    assert closed.json()["error"]["code"] == "HANDOVER_ACTION_RESOLUTION_REQUIRED"

                    second = client.post(
                        root, headers=headers(pm_token, 0),
                        json={**body, "title": "Obsolete follow-up"},
                    )
                    assert second.status_code == 201, second.text
                    cancelled = client.post(
                        root + "/" + second.json()["data"]["action_item_id"] + ":cancel",
                        headers=headers(pm_token, 0), json={"reason": "Superseded by signed response"},
                    )
                    assert cancelled.status_code == 200 and cancelled.json()["data"]["action_state"] == "CANCELLED", cancelled.text

                with connect(name) as db:
                    state = db.execute(
                        "SELECT action_state,lock_version,resolution_trace_ref FROM plm.hnd_action_items "
                        "WHERE action_item_id=%s", (uuid.UUID(action),),
                    ).fetchone()
                    assert state == ("VERIFIED", 4, None), state
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_CLOSED'"
                    ).fetchone()[0] == 0
                print(
                    "HND_02_A05_A04_P02_ACTION_WRITE_HTTP_PASS: Windows composition HTTP "
                    "CREATE/PATCH/START/SUBMIT/VERIFY/CANCEL and fail-closed CLOSE verified "
                    "on PostgreSQL 18"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
