"""Windows PROJECT Reference List composition over disposable PG18."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_project_reference_list_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec


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


def on_created(*, runtime, audit, license_guard, project, other_project,
               created, member_created, token, **_unused) -> int:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(),
        audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    cursors = ReferenceListCursorCodec(b"r" * 32)
    router = create_windows_project_reference_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=cursors)
    path = f"/api/v1/projects/{project}/reference-solutions"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    with TestClient(create_app(), base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 404
    with TestClient(create_app(project_reference_list_router=router),
                    base_url="https://plm.example.test") as client:
        assert client.post(path, headers=headers).status_code == 404
        first = client.get(path + "?page_size=1", headers=headers)
        assert first.status_code == 200, first.text
        first_data = first.json()["data"]
        assert first_data["has_more"] and len(first_data["items"]) == 1
        cursor = first_data["next_cursor"]
        second = client.get(path, params={"page_size": "1", "cursor": cursor},
                            headers=headers)
        assert second.status_code == 200, second.text
        second_data = second.json()["data"]
        assert not second_data["has_more"]
        assert {item["reference_solution_id"] for item in (
            first_data["items"] + second_data["items"])} == {
                str(created.reference_solution_id),
                str(member_created.reference_solution_id)}
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
    denied = create_windows_project_reference_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=DeniedLicense(), cursors=cursors)
    with TestClient(create_app(project_reference_list_router=denied),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 403
    return 0


def main() -> None:
    project_fixture.main(on_created=on_created)
    print("SOL_01_A04_P04_P06_REFERENCE_LIST_WINDOWS_PG_PASS: Windows List "
          "composition, real Session/ASGI/PG, default route closed, read-only POST "
          "404 and License denied")


if __name__ == "__main__":
    main()
