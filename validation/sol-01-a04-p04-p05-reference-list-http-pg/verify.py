"""PROJECT Reference List signed cursor through real Session/ASGI/PG."""

from __future__ import annotations

import importlib.util
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
from plm_assistant.modules.solution.api.reference_list import create_project_reference_list_router
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.application.read_reference import ReferenceReadService
from plm_assistant.modules.solution.infrastructure.reference_read_repository import SqlAlchemyReferenceReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
project_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def _service(runtime, guard):
    return ReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyReferenceReadRepository())


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               member, created, member_created, token, member_token,
               **_unused) -> int:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(),
        audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    cursors = ReferenceListCursorCodec(b"k" * 32)
    router = create_project_reference_list_router(
        sessions=sessions, origins=origins,
        reads=_service(runtime, license_guard), cursors=cursors)
    path = f"/api/v1/projects/{project}/reference-solutions"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex()}
    with TestClient(create_app(project_reference_list_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.get(path + "?page_size=1", headers=headers)
        assert first.status_code == 200, first.text
        first_data = first.json()["data"]
        assert first_data["has_more"] and len(first_data["items"]) == 1
        cursor = first_data["next_cursor"]
        second = client.get(path, params={"page_size": "1", "cursor": cursor},
                            headers=headers)
        assert second.status_code == 200, second.text
        second_data = second.json()["data"]
        assert not second_data["has_more"] and second_data["next_cursor"] is None
        assert {item["reference_solution_id"] for item in (
            first_data["items"] + second_data["items"])} == {
                str(created.reference_solution_id),
                str(member_created.reference_solution_id)}
        assert all(item["scope"] == "PROJECT" and item["project_id"] == str(project)
                   and "document_version_ids" not in item
                   for item in first_data["items"] + second_data["items"])
        assert client.get(path + "?page_size=2&cursor=" + cursor,
                          headers=headers).status_code == 400
        assert client.get(path + "?page_size=1&cursor=" + cursor,
                          headers=member_headers).status_code == 400
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert client.get(path, headers=member_headers).status_code == 200
        assert client.get(path, headers={**headers,
            "cookie": "plm_session=" + (b"u" * 32).hex()}).status_code == 200
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
        assert client.get(path, headers=member_headers).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
    denied_router = create_project_reference_list_router(
        sessions=sessions, origins=origins,
        reads=_service(runtime, DeniedLicense()), cursors=cursors)
    with TestClient(create_app(project_reference_list_router=denied_router),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 403
    return 0


def main() -> None:
    project_fixture.main(on_created=on_created)
    print("SOL_01_A04_P04_P05_REFERENCE_LIST_HTTP_PG_PASS: real Session/ASGI/PG "
          "two pages, signed bindings, project/member/License denial")


if __name__ == "__main__":
    main()
