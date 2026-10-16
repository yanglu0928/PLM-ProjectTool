"""Win11 isolated ASGI/PG proof for opt-in SolutionOutline list HTTP."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.outline_list import create_outline_list_router
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.application.read_outline import OutlineReadService
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_list_owner_fixture",
    ROOT / "validation/sol-02-a06-p04-outline-list-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("EXPIRED")


def on_created(*, runtime, audit, license_guard, project, other_project,
               token, member_token, create_router_factory=None, **kwargs):
    prior.on_created(runtime=runtime, audit=audit,
                     license_guard=license_guard, project=project,
                     other_project=other_project, token=token,
                     member_token=member_token, **kwargs)
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    reader = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyOutlineReadRepository())
    codec = OutlineListCursorCodec(b"o" * 32)
    router = (create_outline_list_router(
        sessions=sessions, origins=origins, reads=reader, cursors=codec)
        if create_router_factory is None else create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard, cursors=codec))
    path = f"/api/v1/projects/{project}/solution-outlines"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    with TestClient(create_app(), base_url="https://plm.example.test") as default:
        assert default.get(path, headers=headers).status_code == 404
    with TestClient(create_app(solution_outline_list_router=router),
                    base_url="https://plm.example.test") as client:
        assert client.post(path, headers=headers).status_code == 404
        ids = []
        cursor = None
        for index in range(3):
            params = {"page_size": "1"}
            if cursor is not None:
                params["cursor"] = cursor
            response = client.get(path, params=params, headers=headers)
            assert response.status_code == 200, response.text
            payload = response.json()["data"]
            assert len(payload["items"]) == 1
            item = payload["items"][0]
            assert item["current_approved_version_ref"] is None
            assert set(item) == {
                "solution_outline_id", "project_id", "name", "outline_state",
                "current_approved_version_ref", "created_at", "etag"}
            ids.append(uuid.UUID(item["solution_outline_id"]))
            assert payload["has_more"] == (index < 2)
            cursor = payload["next_cursor"]
        assert ids == sorted(ids, key=lambda value: value.int)
        assert len(set(ids)) == 3 and cursor is None
        first_cursor = codec.encode(
            session_token=token, project_id=project, page_size=1,
            outline_id=ids[0])
        assert client.get(path, params={"page_size": "2", "cursor": first_cursor},
                          headers=headers).status_code == 400
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert client.get(path, headers={"cookie": "plm_session="
                          + member_token.hex(),
                          "origin": "https://plm.example.test"}).status_code == 404
        assert client.get(path, headers={}).status_code == 401
        assert client.get(path, headers={**headers,
               "origin": "https://evil.test"}).status_code == 403
    denied = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=DeniedLicense(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyOutlineReadRepository())
    denied_router = create_outline_list_router(
        sessions=sessions, origins=origins, reads=denied, cursors=codec)
    with TestClient(create_app(solution_outline_list_router=denied_router),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 403
    return 0


if __name__ == "__main__":
    prior.prior.prior.main(on_created=on_created)
    print("SOL_02_A06_P07_OUTLINE_LIST_HTTP_PG_PASS: default closed, "
          "real ASGI/Session/PG three pages, cursor and denied scopes")
