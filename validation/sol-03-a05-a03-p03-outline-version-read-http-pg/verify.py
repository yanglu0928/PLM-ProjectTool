"""Disposable Win11 ASGI/PG check of opt-in PROJECT/GLOBAL history reads."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.solution.api.outline_version_list_cursor import OutlineVersionListCursorCodec
from plm_assistant.modules.solution.api.outline_version_read import create_outline_version_read_router


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_history_owner_for_http",
    ROOT / "validation/sol-03-a05-a02-p02-outline-version-read-owner/verify.py")
assert SPEC and SPEC.loader
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)


def _client(*, runtime, audit, license_guard):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    router = create_outline_version_read_router(
        sessions=sessions, origins=LoginOriginPolicy(["https://plm.example.test"]),
        reads=previous._service(runtime, license_guard),
        cursors=OutlineVersionListCursorCodec(b"h" * 32))
    return TestClient(create_app(solution_outline_version_read_router=router),
                      base_url="https://plm.example.test")


def _headers(token):
    return {"cookie": "plm_session=" + token.hex(),
            "origin": "https://plm.example.test"}


def _check(*, runtime, audit, license_guard, project, outline,
           token, scope, expected, reader_token=None):
    path = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
    with _client(runtime=runtime, audit=audit, license_guard=license_guard) as app:
        first = app.get(path, params={"page_size": "1"}, headers=_headers(token))
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "no-store"
        page = first.json()["data"]
        assert page["items"][0]["version_no"] == expected
        assert page["items"][0]["declared_reference_count"] == 1
        assert "reference_refs" not in page["items"][0]
        version = page["items"][0]["solution_outline_version_id"]
        detail = app.get(path + "/" + version, headers=_headers(token))
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["reference_refs"][0]["scope"] == scope
        assert len(detail.json()["data"]["section_ids"]) == 1
        assert len(detail.json()["data"]["requirement_refs"]) == 1
        assert "etag" not in detail.headers
        assert app.post(path, headers=_headers(token), json={}).status_code == 404
        if expected > 1:
            assert page["has_more"] and page["next_cursor"]
            second = app.get(path, params={
                "page_size": "1", "cursor": page["next_cursor"]},
                headers=_headers(token))
            assert second.status_code == 200, second.text
            assert second.json()["data"]["items"][0]["version_no"] == 1
            assert not second.json()["data"]["has_more"]
            assert app.get(path, params={
                "page_size": "2", "cursor": page["next_cursor"]},
                headers=_headers(token)).status_code == 400
        else:
            assert not page["has_more"] and page["next_cursor"] is None
        assert app.get(path.replace(str(project), str(uuid.uuid4())),
                       headers=_headers(token)).status_code == 404
        assert app.get(path + "/" + str(uuid.uuid4()),
                       headers=_headers(token)).status_code == 404
        assert app.get(path, headers=_headers(b"x" * 32)).status_code == 401
        assert app.get(path, headers={**_headers(token),
                                      "origin": "https://evil.test"}).status_code == 403
        if reader_token is not None:
            assert app.get(path, headers=_headers(reader_token)).status_code == 200
        with _client(runtime=runtime, audit=audit,
                     license_guard=previous.DeniedLicense()) as denied:
            assert denied.get(path, headers=_headers(token)).status_code == 403
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.get(path, headers=_headers(token)).status_code == 404
        assert bare.get(path + "/" + version,
                        headers=_headers(token)).status_code == 404


def project_created(**kwargs):
    previous.project_created(**kwargs)
    project = kwargs["project"]
    outline = previous.previous._ids(kwargs["port"], project, "PROJECT")[0][0]
    _check(runtime=kwargs["runtime"], audit=kwargs["audit"],
           license_guard=kwargs["license_guard"], project=project,
           outline=outline, token=kwargs["token"], scope="PROJECT",
           expected=2, reader_token=kwargs["member_token"])
    return 0


def global_qualified(**kwargs):
    previous.global_qualified(**kwargs)
    project = previous.previous._global_project(kwargs["port"])
    outline = previous.previous._ids(kwargs["port"], project, "GLOBAL")[0][0]
    _check(runtime=kwargs["runtime"], audit=kwargs["audit"],
           license_guard=kwargs["license_guard"], project=project,
           outline=outline, token=b"y" * 32, scope="GLOBAL", expected=1)
    return 0


if __name__ == "__main__":
    previous.previous.previous.fixture.main(on_created=project_created)
    previous.previous.previous.composition.global_fixture.main(
        on_qualified=global_qualified)
    print("SOL_03_A05_A03_P03_OUTLINE_VERSION_READ_HTTP_PG_PASS: "
          "PROJECT/GLOBAL ASGI/PG history, cursor, role/Auth/License, default 404")
