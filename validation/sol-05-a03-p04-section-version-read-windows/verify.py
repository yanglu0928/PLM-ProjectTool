"""Disposable Win11 ASGI/PG proof for Windows SectionVersion history read."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_section_version_read_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_history_owner_fixture",
    ROOT / "validation/sol-05-a03-p02-section-version-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def headers(token: bytes) -> dict[str, str]:
    return {"cookie": "plm_session=" + token.hex(),
            "origin": "https://plm.example.test"}


def on_http(*, port, runtime, audit, license_guard, project, other_project,
            token, member_token, section, document_version, evidence,
            requirement, requirement_version, **_unused):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    args = dict(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard,
        cursors=SectionVersionListCursorCodec(b"h" * 32),
    )
    for key in ("runtime", "sessions", "origins", "license_guard", "cursors"):
        try:
            create_windows_section_version_read_router(**{**args, key: None})
        except ProductionSolutionOutlineStartupError:
            pass
        else:
            raise AssertionError("missing read trust mounted route: " + key)
    router = create_windows_section_version_read_router(**args)
    path = f"/api/v1/projects/{project}/solution-sections/{section}/versions"
    with TestClient(create_app(solution_section_version_read_router=router),
                    base_url="https://plm.example.test") as app:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            assert bare.get(path, headers=headers(token)).status_code == 404
        seen = []
        cursor = None
        for expected in ((5, 4), (3, 2), (1,)):
            params = {"page_size": "2"}
            if cursor is not None:
                params["cursor"] = cursor
            response = app.get(path, params=params, headers=headers(token))
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            data = response.json()["data"]
            assert tuple(item["version_no"] for item in data["items"]) == expected
            assert all("evidence_ids" not in item for item in data["items"])
            seen.extend(data["items"])
            cursor = data["next_cursor"]
        assert cursor is None and len(seen) == 5
        latest = seen[0]["solution_section_version_id"]
        detail = app.get(path + "/" + latest, headers=headers(token))
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["content_document_version_ref"] == str(
            document_version)
        assert detail.json()["data"]["evidence_ids"] == [str(evidence)]
        assert detail.json()["data"]["requirement_refs"] == [{
            "requirement_id": str(requirement),
            "requirement_version_id": str(requirement_version)}]
        assert app.get(path + "/" + latest,
                       headers=headers(member_token)).status_code == 200
        assert app.get(path, headers={}).status_code == 401
        assert app.get(path, headers=headers(b"x" * 32)).status_code == 401
        assert app.get(f"/api/v1/projects/{other_project}/solution-sections/"
                       f"{section}/versions", headers=headers(token)).status_code == 404
        assert app.get(path + "/" + str(uuid.uuid4()),
                       headers=headers(token)).status_code == 404
        assert app.post(path, headers=headers(token)).status_code == 404
        first = app.get(path, params={"page_size": "1"}, headers=headers(token))
        signed = first.json()["data"]["next_cursor"]
        assert signed
        for params, caller in (
            ({"page_size": "2", "cursor": signed}, token),
            ({"page_size": "1", "cursor": signed}, member_token),
            ({"page_size": "1", "cursor": "A" + signed[1:]}, token),
        ):
            assert app.get(path, params=params,
                           headers=headers(caller)).status_code == 400
    denied = create_windows_section_version_read_router(
        **{**args, "license_guard": prior.DeniedLicense()})
    with TestClient(create_app(solution_section_version_read_router=denied),
                    base_url="https://plm.example.test") as app:
        assert app.get(path, headers=headers(token)).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_SECTION_VERSION_CREATED'").fetchone()[0] == 5
    print("SOL_05_A03_P04_SECTION_VERSION_READ_WINDOWS_PG_PASS: five versions, "
          "Windows factory, pagination, detail, isolation, auth/license and no writes")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=on_http))
