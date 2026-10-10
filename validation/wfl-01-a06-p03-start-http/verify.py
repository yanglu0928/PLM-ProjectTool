"""Opt-in Workflow start HTTP against isolated real Session and PostgreSQL 18."""

from __future__ import annotations

import argparse
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.workflow.api.start_workflow import create_workflow_start_router
from plm_assistant.modules.workflow.application.start_workflow import WorkflowStartService
from plm_assistant.modules.workflow.infrastructure.read_repository import SqlAlchemyWorkflowReadRepository
from plm_assistant.modules.workflow.infrastructure.start_repository import SqlAlchemyWorkflowStartRepository


SOURCE = Path(__file__).resolve().parents[1] / "wfl-01-a06-p02-start-service" / "verify.py"
spec = spec_from_file_location("_workflow_start_service_seed", SOURCE)
seed = module_from_spec(spec)
spec.loader.exec_module(seed)
cluster = seed.cluster
fixture = seed.fixture
composition_check = None


def _matrix() -> None:
    name = "wflhttp_" + uuid.uuid4().hex[:12]
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                             host="127.0.0.1", port=cluster.PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            runtime = create_database_runtime(url)
            token, member_token = b"s" * 32, b"m" * 32
            with fixture.connect(name) as db:
                pm = seed._user(db, "Workflow HTTP Manager", token)
                member = seed._user(db, "Workflow HTTP Member", member_token)
                with db.transaction():
                    project = fixture.insert(db, "prj_projects", dict(
                        project_code="WHTTP", project_code_normalized="whttp",
                        name="Synthetic Workflow HTTP", created_by=pm), "project_id")
                    department = fixture.insert(db, "prj_departments", dict(
                        project_id=project, department_code="D",
                        department_code_normalized="d", name="Department"), "department_id")
                    for user_id, role in ((pm, "PROJECT_MANAGER"),
                                          (member, "IMPLEMENTATION_MEMBER")):
                        fixture.insert(db, "prj_project_members", dict(
                            project_id=project, user_id=user_id,
                            department_id=department, project_role=role),
                            "project_member_id")
                    workflow_id = fixture.initialize(db, project, pm)

            guard = seed.Guard()
            audit = AuditService(SqlAlchemyAuditRepository())
            reader = SqlAlchemyWorkflowReadRepository()
            starts = WorkflowStartService(
                unit_of_work=runtime.unit_of_work,
                sessions=SqlAlchemyProjectWriteAccess(),
                projects=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository()),
                license_guard=guard,
                starter=SqlAlchemyWorkflowStartRepository(reader=reader),
                reader=reader, receipts=SqlAlchemyIdempotencyReceipts(),
                audit=audit,
            )
            sessions = SessionService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemySessionRepository(),
                issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
                audit=audit,
            )
            router = create_workflow_start_router(
                sessions=sessions, workflows=starts,
                origins=LoginOriginPolicy(["http://localhost"]),
            )
            path = f"/api/v1/projects/{project}/workflow:start"
            headers = {"cookie": "plm_session=" + token.hex(),
                       "x-csrf-token": seed.CSRF.hex(),
                       "idempotency-key": "workflow-http-key-123",
                       "if-match": '"v0"', "origin": "http://localhost"}
            with TestClient(create_app(), base_url="http://localhost") as closed:
                assert closed.post(path, headers=headers).status_code == 404
            with TestClient(create_app(workflow_start_router=router),
                            base_url="http://localhost") as client:
                def expect(request_headers, status, code=None, url=path, content=None):
                    response = client.post(url, headers=request_headers, content=content)
                    assert response.status_code == status, response.text
                    if code is not None:
                        assert response.json()["error"]["code"] == code, response.text
                    return response

                expect(headers | {"cookie": "plm_session=" + member_token.hex()},
                       404, "RESOURCE_NOT_FOUND")
                expect({key: value for key, value in headers.items() if key != "if-match"},
                       428, "CONFLICT_VERSION_REQUIRED")
                expect(headers | {"x-csrf-token": (b"x" * 32).hex()},
                       403, "AUTH_CSRF_INVALID")
                expect(headers | {"host": "evil.invalid"}, 403, "AUTH_CSRF_INVALID")
                guard.enabled = False
                expect(headers, 403, "LICENSE_OPERATION_DENIED")
                guard.enabled = True
                first = expect(headers, 200)
                assert first.headers["etag"] == '"v1"'
                assert first.headers["cache-control"] == "no-store"
                assert first.json()["data"]["workflow_id"] == str(workflow_id)
                assert first.json()["data"]["current_stage"] == "HANDOVER"
                assert len(first.json()["data"]["stages"]) == 6
                replay = expect(headers, 200)
                assert replay.json()["data"] == first.json()["data"]
                expect(headers | {"if-match": '"v1"'}, 409,
                       "CONFLICT_IDEMPOTENCY")
                expect(headers | {"idempotency-key": "workflow-http-key-456"},
                       409, "CONFLICT_VERSION")
                expect(headers, 400, "REQUEST_MALFORMED", content=b"{}")
                expect(headers, 400, "REQUEST_MALFORMED", url=path + "?extra=1")
            with fixture.connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='WORKFLOW_STARTED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                  "WHERE operation='V1_WORKFLOW_START' AND state='COMPLETED'").fetchone()[0] == 1
                assert db.execute("SELECT workflow_state,current_stage_key,lock_version "
                                  "FROM plm.wfl_project_workflows WHERE workflow_id=%s",
                                  (workflow_id,)).fetchone() == ("ACTIVE", "HANDOVER", 1)
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 0
            if composition_check is not None:
                composition_check(url, name, guard)
            print("Workflow start HTTP PASS: opt-in ASGI/PG18 real Session/CSRF/PM/"
                  "initial/replay/error contract/one Audit; default 404 and no Gate", flush=True)
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    options = parser.parse_args()
    cluster._matrix = _matrix
    cluster.verify(options.pg_bin, options.temp_root)
