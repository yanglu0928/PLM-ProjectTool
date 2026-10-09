"""Win11 isolated ASGI/PG18 project GLOBAL candidate GET proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.global_reference_candidates import (
    create_project_global_reference_candidate_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_owner_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p05-a03-global-candidate-owner/verify.py")
assert SPEC and SPEC.loader
owner_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owner_fixture)
fixture = owner_fixture.fixture


class Sessions:
    def validate(self, token):
        if token != fixture.TOKEN:
            raise SessionError("AUTH_SESSION_EXPIRED")


def on_http(*, reader, project, other_project, initial) -> None:
    path = f"/api/v1/projects/{project}/global-reference-candidates"
    other_path = f"/api/v1/projects/{other_project}/global-reference-candidates"
    headers = {
        "cookie": "plm_session=" + fixture.TOKEN.hex(),
        "origin": "https://plm.example.test",
    }
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.get(path, headers=headers).status_code == 404
    router = create_project_global_reference_candidate_router(
        sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
        reads=reader)
    with TestClient(create_app(project_global_reference_candidate_router=router),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers={**headers,
                                         "origin": "https://evil.test"}).status_code == 403
        assert client.get(path, headers={"origin": headers["origin"]}).status_code == 401
        assert client.get(other_path, headers=headers).status_code == 404
        first = client.get(path + "?page_size=1", headers=headers)
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "no-store"
        assert first.json()["data"]["items"] == []
        assert first.json()["data"]["has_more"]
        cursor = first.json()["data"]["next_cursor"]
        assert cursor
        assert client.get(path + "?page_size=2&cursor=" + cursor,
                          headers=headers).status_code == 400
        second = client.get(path, params={"page_size": "1", "cursor": cursor},
                            headers=headers)
        assert second.status_code == 200, second.text
        page = second.json()["data"]
        assert not page["has_more"] and page["next_cursor"] is None
        assert len(page["items"]) == 1
        item = page["items"][0]
        assert item["reference_solution_id"] == str(initial.reference_solution_id)
        assert item["reference_version_id"] == str(initial.reference_version_id)
        assert item["display_label"] == "审定的合成标签"
        assert set(item) == {
            "reference_solution_id", "reference_version_id", "display_label",
            "version_no", "eligibility_state"}
        assert "Synthetic unreviewed raw name" not in second.text
        assert "source_fingerprint" not in second.text
        assert client.post(path, headers=headers).status_code == 404


def on_qualified(**facts) -> None:
    owner_fixture.internal.on_qualified(
        **facts, on_published=lambda **published:
        owner_fixture.on_published(**published, on_http=on_http))


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
    print("SOL_03_A04_P03_P03_P06_A03_P05_A04_GLOBAL_CANDIDATE_HTTP_PG_PASS")
