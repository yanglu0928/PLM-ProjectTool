"""Win11 isolated ASGI/PG proof for opt-in SolutionSection LIST."""

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
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.section_list import create_section_list_router
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.application.read_section import SectionReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_list_owner_fixture",
    ROOT / "validation/sol-04-a11-section-list-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               member, token, member_token, create_router_factory=None,
               **kwargs) -> int:
    prior.on_created(
        port=port, runtime=runtime, audit=audit,
        license_guard=license_guard, project=project,
        other_project=other_project, member=member,
        token=token, member_token=member_token, **kwargs)
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemySectionReadRepository())
    origins = LoginOriginPolicy(["https://plm.example.test"])
    cursors = SectionListCursorCodec(b"q" * 32)
    router = (create_section_list_router(
        sessions=sessions, origins=origins,
        reads=SectionReadService(**common, license_guard=license_guard),
        cursors=cursors)
        if create_router_factory is None else create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard, cursors=cursors))
    path = f"/api/v1/projects/{project}/solution-sections"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.get(path, headers=headers).status_code == 404
    with TestClient(create_app(solution_section_list_router=router),
                    base_url="https://plm.example.test") as client:
        assert client.post(path, headers=headers, json={}).status_code == 404
        seen = []
        cursor = None
        for index in range(3):
            url = path + "?page_size=1"
            if cursor is not None:
                url += "&cursor=" + cursor
            result = client.get(url, headers=headers)
            assert result.status_code == 200, result.text
            assert result.headers["cache-control"] == "no-store"
            assert result.headers["x-trace-id"] == result.json()["trace_id"]
            data = result.json()["data"]
            assert len(data["items"]) == 1
            item = data["items"][0]
            assert item["project_id"] == str(project)
            assert item["section_key"] in {"Scope", "Section 2", "Section 3"}
            assert item["current_approved_version_ref"] is None
            assert item["etag"] == '"v0"'
            seen.append(uuid.UUID(item["solution_section_id"]))
            assert data["has_more"] is (index < 2)
            cursor = data["next_cursor"]
            if index == 0:
                first_cursor = cursor
        assert seen == sorted(seen) and len(set(seen)) == 3 and cursor is None
        assert len(client.get(path, headers=headers).json()["data"]["items"]) == 3
        assert client.get(path + "?page_size=1&cursor=" + first_cursor,
                          headers={**headers, "cookie": "plm_session=" +
                                   member_token.hex()}).status_code == 400
        assert client.get(path + "?page_size=2&cursor=" + first_cursor,
                          headers=headers).status_code == 400
        assert client.get(path.replace(str(project), str(other_project)) +
                          "?page_size=1&cursor=" + first_cursor,
                          headers=headers).status_code == 400
        changed = "A" if first_cursor[-1] != "A" else "B"
        assert client.get(path + "?page_size=1&cursor=" + first_cursor[:-1] + changed,
                          headers=headers).status_code == 400
        assert client.get(path + "?page_size=1&page_size=1", headers=headers).status_code == 400
        assert client.get(path + "?after_section_id=" + str(seen[0]),
                          headers=headers).status_code == 400
        assert client.get(path + "?page_size=0", headers=headers).status_code == 422
        assert client.get(path, headers={}).status_code == 401
        assert client.get(path, headers={**headers, "origin": "https://evil.test"}).status_code == 403
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert len(client.get(path, headers={"cookie": "plm_session=" +
                            member_token.hex(), "origin": "https://plm.example.test"}
                            ).json()["data"]["items"]) == 3
        assert len(client.get(path, headers={"cookie": "plm_session=" +
                            (b"u" * 32).hex(), "origin": "https://plm.example.test"}
                            ).json()["data"]["items"]) == 3
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
        assert client.get(path, headers={"cookie": "plm_session=" +
                          member_token.hex(), "origin": "https://plm.example.test"}
                          ).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
    denied_router = (create_section_list_router(
        sessions=sessions, origins=origins,
        reads=SectionReadService(**common, license_guard=DeniedLicense()),
        cursors=cursors)
        if create_router_factory is None else create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=DeniedLicense(), cursors=cursors))
    with TestClient(create_app(solution_section_list_router=denied_router),
                    base_url="https://plm.example.test") as client:
        denied = client.get(path, headers=headers)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    return 0


if __name__ == "__main__":
    prior.prior.fixture.main(on_created=on_created)
    print("SOL_04_A14_SECTION_LIST_HTTP_PG_PASS: default closed, real "
          "ASGI/Session/PG three-page cursor, roles, isolation and License")
