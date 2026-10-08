"""Windows GLOBAL List composition against isolated PG18 Create fixture."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import create_windows_global_reference_list_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_create_pg",
    ROOT / "validation/sol-01-a04-p08-p06-p03-global-reference-create-http-pg/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def check(*, runtime, license_guard, result, **_unused):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(),
        audit=object())
    origins = LoginOriginPolicy(["https://plm.example.test"])
    codec = GlobalReferenceListCursorCodec(b"g" * 32)
    router = create_windows_global_reference_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=codec)
    path = "/api/v1/global/reference-solutions"
    headers = {"cookie": "plm_session=" + base.fixture.TOKEN.hex(),
               "origin": "https://plm.example.test"}
    identity = uuid.UUID(result["reference_solution_id"])
    with TestClient(create_app(global_reference_list_router=router),
                    base_url="https://plm.example.test") as client:
        response = client.get(path + "?page_size=1", headers=headers)
        assert response.status_code == 200, response.text
        page = response.json()["data"]
        assert len(page["items"]) == 1 and not page["has_more"]
        assert page["next_cursor"] is None
        assert page["items"][0]["reference_solution_id"] == str(identity)
        assert page["items"][0]["scope"] == "GLOBAL"
        assert page["items"][0]["project_id"] is None
        assert "document_refs" not in page["items"][0]
        assert "deidentification_confirmation_id" not in page["items"][0]
        cursor = codec.encode(session_token=base.fixture.TOKEN, page_size=1,
                              reference_solution_id=identity)
        after = client.get(path, params={"page_size": "1", "cursor": cursor},
                           headers=headers)
        assert after.status_code == 200 and after.json()["data"]["items"] == []
        project_cursor = ReferenceListCursorCodec(b"g" * 32).encode(
            session_token=base.fixture.TOKEN, project_id=uuid.uuid4(),
            page_size=1, reference_solution_id=identity)
        assert client.get(path, params={"page_size": "1", "cursor": project_cursor},
                          headers=headers).status_code == 400
        assert client.get(path, params={"page_size": "2", "cursor": cursor},
                          headers=headers).status_code == 400
        assert client.get(path, params={"page_size": "1", "cursor": "A" + cursor[1:]},
                          headers=headers).status_code == 400
        assert client.get(path, headers={"origin": headers["origin"]}).status_code == 401
        assert client.get(path, headers={**headers, "origin": "https://evil.test"}).status_code == 403
        assert client.post(path, headers=headers).status_code == 404
    denied = create_windows_global_reference_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=DeniedLicense(), cursors=codec)
    with TestClient(create_app(global_reference_list_router=denied),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 403


def on_preview(**kwargs):
    base.on_preview(**kwargs, on_created=check, on_revoked=check)


def main():
    base.fixture.main(on_preview=on_preview)
    print("SOL_01_A04_P09_P04_GLOBAL_REFERENCE_LIST_HTTP_PG_PASS")


if __name__ == "__main__":
    main()
