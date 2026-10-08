"""Real ASGI/PG POST for opt-in SOL_OUTLINE_CREATE on synthetic identities."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.outline_create import create_outline_create_router
from plm_assistant.modules.solution.application.create_outline import OutlineCreateService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager, member, token, csrf, member_token, member_csrf,
               **_unused) -> int:
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit,
    )
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyOutlineCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    service = OutlineCreateService(**dependencies, license_guard=license_guard)
    router = create_outline_create_router(sessions=sessions, origins=origins, creates=service)
    path = f"/api/v1/projects/{project}/solution-outlines"
    headers = {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": "h" * 16,
    }
    with TestClient(create_app(solution_outline_create_router=router),
                    base_url="https://plm.example.test") as client:
        created = client.post(path, headers=headers, json={"name": "HTTP outline"})
        assert created.status_code == 201, created.text
        data = created.json()["data"]
        assert data["outline_state"] == "ACTIVE" and data["current_approved_version_ref"] is None
        assert data["project_id"] == str(project) and created.headers["etag"] == '"v0"'
        assert created.headers["location"].endswith(data["solution_outline_id"])
        assert created.headers["x-trace-id"] == created.json()["trace_id"]
        assert client.post(path, headers=headers, json={"name": "HTTP outline"}).json()["data"] == data
        assert client.post(path, headers=headers, json={"name": "Different"}).status_code == 409
        member_headers = {
            **headers, "cookie": "plm_session=" + member_token.hex(),
            "x-csrf-token": member_csrf.hex(), "idempotency-key": "m" * 16,
        }
        assert client.post(path, headers=member_headers,
                           json={"name": "Member outline"}).status_code == 201
        customer_headers = {
            **headers, "cookie": "plm_session=" + (b"u" * 32).hex(),
            "x-csrf-token": (b"v" * 32).hex(), "idempotency-key": "c" * 16,
        }
        assert client.post(path, headers=customer_headers,
                           json={"name": "Customer denied"}).status_code == 404
        assert client.post(f"/api/v1/projects/{other_project}/solution-outlines",
                           headers=headers, json={"name": "Cross project"}).status_code == 404
        assert client.post(path, headers={**headers, "x-csrf-token": (b"x" * 32).hex()},
                           json={"name": "Bad csrf"}).status_code == 403
        assert client.post(path, headers={**headers, "cookie": "plm_session=" +
                           (b"z" * 32).hex()}, json={"name": "Bad session"}).status_code == 401
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
        assert client.post(path, headers=headers, json={"name": "HTTP outline"}).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
    denied = OutlineCreateService(**dependencies, license_guard=DeniedLicense())
    denied_router = create_outline_create_router(
        sessions=sessions, origins=origins, creates=denied)
    with TestClient(create_app(solution_outline_create_router=denied_router),
                    base_url="https://plm.example.test") as client:
        refused = client.post(path, headers={**headers, "idempotency-key": "l" * 16},
                              json={"name": "License denied"})
        assert refused.status_code == 403
        assert refused.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json={"name": "Closed"}).status_code == 404
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_outlines WHERE project_id=%s",
                          (project,)).fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='SOL_OUTLINE_CREATED' AND target_project_id=%s",
                          (project,)).fetchone()[0] == 2
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("SOL_02_A04_OUTLINE_CREATE_HTTP_PG_PASS: real Session/ASGI/PG, "
          "replay, roles, CSRF, License, closed default")
