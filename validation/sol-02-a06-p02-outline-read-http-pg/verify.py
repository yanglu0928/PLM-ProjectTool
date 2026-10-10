"""Win11 isolated ASGI/PG proof for opt-in SolutionOutline detail GET."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.outline_read import create_outline_read_router
from plm_assistant.modules.solution.application.read_outline import OutlineReadService
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_read_owner_fixture",
    ROOT / "validation/sol-02-a06-p01-outline-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               token, member_token, create_router_factory=None, **kwargs):
    prior.on_created(port=port, runtime=runtime, audit=audit,
                     license_guard=license_guard, project=project,
                     other_project=other_project, token=token,
                     member_token=member_token, **kwargs)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        outline_id = db.execute(
            "SELECT solution_outline_id FROM plm.sol_outlines "
            "WHERE project_id=%s AND name='Read target'", (project,)).fetchone()[0]
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    reader = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyOutlineReadRepository())
    origins = LoginOriginPolicy(["https://plm.example.test"])
    router = (create_outline_read_router(
        sessions=sessions, origins=origins, reads=reader)
        if create_router_factory is None else create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard))
    path = f"/api/v1/projects/{project}/solution-outlines/{outline_id}"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    with TestClient(create_app(), base_url="https://plm.example.test") as default:
        assert default.get(path, headers=headers).status_code == 404
    with TestClient(create_app(solution_outline_read_router=router),
                    base_url="https://plm.example.test") as client:
        good = client.get(path, headers=headers)
        assert good.status_code == 200, good.text
        assert good.headers["etag"] == '"v0"'
        assert good.json()["data"]["current_approved_version_ref"] is None
        assert good.json()["data"]["solution_outline_id"] == str(outline_id)
        assert client.get(path, headers={}).status_code == 401
        assert client.get(path, headers={**headers,
               "origin": "https://evil.test"}).status_code == 403
        assert client.get(path + "?x=1", headers=headers).status_code == 400
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert client.get(path.replace(str(outline_id), str(uuid.uuid4())),
                          headers=headers).status_code == 404
        assert client.get(path, headers={"cookie": "plm_session="
                          + member_token.hex(),
                          "origin": "https://plm.example.test"}).status_code == 404
    return 0


if __name__ == "__main__":
    prior.prior.main(on_created=on_created)
    print("SOL_02_A06_P02_OUTLINE_READ_HTTP_PG_PASS: default closed, "
          "real ASGI/Session/PG, ETag, isolation and revoked member")
