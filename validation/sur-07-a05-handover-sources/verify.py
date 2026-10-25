"""Win11/PG18 HTTP proof for current approved Handover Survey sources.

Requires an isolated synthetic PostgreSQL cluster on 127.0.0.1:55434.
The reused Handover fixture creates and drops its own uniquely named database.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_handover import (
    HANDOVER_ANALYSIS_CURSOR_KEY_REF, HANDOVER_ITEM_CURSOR_KEY_REF,
    HANDOVER_VERSION_CURSOR_KEY_REF, create_windows_handover_routers,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.handover.api.read_cursor import (
    HandoverSurveySourceCursorCodec,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/hnd-01-a04-a02-p02-review-owner/verify.py"
spec = importlib.util.spec_from_file_location("sur07a05_handover_fixture", SOURCE)
assert spec and spec.loader
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class Keys:
    def resolve_key(self, key_ref):
        return {
            HANDOVER_ANALYSIS_CURSOR_KEY_REF: b"a" * 32,
            HANDOVER_VERSION_CURSOR_KEY_REF: b"v" * 32,
            HANDOVER_ITEM_CURSOR_KEY_REF: b"i" * 32,
        }.get(key_ref)


def client_for(runtime, guard, manager_token, reviewer_token):
    class Sessions:
        def validate(self, token):
            if token not in (manager_token, reviewer_token):
                raise ValueError("invalid synthetic session")

    origins = LoginOriginPolicy(["http://localhost"])
    routers = create_windows_handover_routers(
        runtime, sessions=Sessions(), origins=origins, license_guard=guard,
        audit=object(), include_write=False, resolver=Keys(),
    )
    return TestClient(
        create_app(handover_survey_source_router=routers.survey_sources),
        base_url="http://localhost",
    )


def headers(token):
    return {"cookie": "plm_session=" + token.hex()}


def pre_approval(**ctx):
    with client_for(ctx["runtime"], ctx["guard"], ctx["manager_token"],
                    ctx["reviewer_token"]) as client:
        path = f"/api/v1/projects/{ctx['project']}/survey-handover-sources"
        response = client.get(path, headers=headers(ctx["manager_token"]))
        assert response.status_code == 200, response.text
        assert response.json()["data"]["items"] == []


def approved(**ctx):
    with client_for(ctx["runtime"], ctx["guard"], ctx["manager_token"],
                    ctx["reviewer_token"]) as client:
        path = f"/api/v1/projects/{ctx['project']}/survey-handover-sources"
        manager_headers = headers(ctx["manager_token"])
        response = client.get(path + "?page_size=1", headers=manager_headers)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        data = response.json()["data"]
        assert len(data["items"]) == 1 and not data["has_more"], data
        item = data["items"][0]
        assert uuid.UUID(item["handover_item_row_id"]) != uuid.UUID(
            item["analysis_item_id"]
        )
        assert item["handover_analysis_version_id"] == str(ctx["version_id"])
        assert item["handover_analysis_id"] == str(ctx["analysis_id"])
        assert item["state"] == "CONFIRMED"
        codec = HandoverSurveySourceCursorCodec(b"i" * 32)
        before = codec.encode(
            project_id=ctx["project"], session_token=ctx["manager_token"],
            page_size=1, row_id=uuid.UUID(int=1),
        )
        after = codec.encode(
            project_id=ctx["project"], session_token=ctx["manager_token"],
            page_size=1, row_id=uuid.UUID(item["handover_item_row_id"]),
        )
        before_page = client.get(path + "?page_size=1&cursor=" + before,
                                 headers=manager_headers)
        after_page = client.get(path + "?page_size=1&cursor=" + after,
                                headers=manager_headers)
        assert before_page.status_code == 200 and len(
            before_page.json()["data"]["items"]
        ) == 1
        assert after_page.status_code == 200 and after_page.json()["data"]["items"] == []
        assert client.get(path + "?page_size=2&cursor=" + after,
                          headers=manager_headers).status_code == 400
        assert client.get(path).status_code == 401
        assert client.get(path, headers=headers(ctx["reviewer_token"])).status_code == 404
        wrong_path = f"/api/v1/projects/{uuid.uuid4()}/survey-handover-sources"
        assert client.get(wrong_path, headers=manager_headers).status_code == 404
        malformed = client.get(path + "?page_size=1&page_size=2",
                               headers=manager_headers)
        assert malformed.status_code != 200

        with fixture.connect(ctx["database"]) as db:
            db.execute(
                "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                "WHERE project_id=%s AND user_id=%s",
                (ctx["project"], ctx["manager"]),
            )
        denied = client.get(path, headers=manager_headers)
        assert denied.status_code == 404, denied.text
        with fixture.connect(ctx["database"]) as db:
            db.execute(
                "UPDATE plm.prj_project_members SET state='ACTIVE' "
                "WHERE project_id=%s AND user_id=%s",
                (ctx["project"], ctx["manager"]),
            )
        assert client.get(path, headers=manager_headers).status_code == 200


def history(**ctx):
    with client_for(ctx["runtime"], ctx["guard"], ctx["manager_token"],
                    ctx["manager_token"]) as client:
        path = f"/api/v1/projects/{ctx['project']}/survey-handover-sources"
        response = client.get(path + "?page_size=1",
                              headers=headers(ctx["manager_token"]))
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert len(data["items"]) == 1 and not data["has_more"]
        assert data["items"][0]["handover_analysis_version_id"] == str(
            ctx["approved_version_id"]
        )
        assert data["items"][0]["handover_analysis_version_id"] != str(
            ctx["historical_version_id"]
        )


if __name__ == "__main__":
    fixture.main(read_probe=pre_approval, approved_probe=approved,
                 history_probe=history)
    print("SUR_07_A05_HANDOVER_SOURCES_WINDOWS_HTTP_PG_PASS")
