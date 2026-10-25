"""Disposable Win11 ASGI/PG Plan CREATE/GET/LIST composition proof."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_plan import (
    create_windows_plan_create_router, create_windows_plan_read_routers,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_plan_read_fixture_for_http",
    ROOT / "validation/plan-01-a03-p03-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager, member, token, csrf, member_token, member_csrf,
               **kwargs) -> int:
    prior.on_created(
        port=port, runtime=runtime, audit=audit, license_guard=license_guard,
        project=project, other_project=other_project, manager=manager,
        member=member, token=token, csrf=csrf, member_token=member_token,
        member_csrf=member_csrf, **kwargs)
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    cursors = PlanListCursorCodec(b"p" * 32)
    detail, listing = create_windows_plan_read_routers(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=cursors)
    creation = create_windows_plan_create_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit)
    path = f"/api/v1/projects/{project}/plans"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    write_headers = {**headers, "x-csrf-token": csrf.hex(),
                     "idempotency-key": "w" * 16}
    with TestClient(create_app(), base_url="https://plm.example.test") as default:
        assert default.get(path, headers=headers).status_code == 404
        assert default.post(path, headers=write_headers,
                            json={"name": "Closed"}).status_code == 404
    with TestClient(create_app(plan_read_router=detail, plan_list_router=listing),
                    base_url="https://plm.example.test") as readonly:
        assert readonly.get(path, headers=headers).status_code == 200
        assert readonly.post(path, headers=write_headers,
                             json={"name": "Still closed"}).status_code == 404
    with TestClient(create_app(plan_create_router=creation,
                               plan_read_router=detail, plan_list_router=listing),
                    base_url="https://plm.example.test") as client:
        created = client.post(path, headers=write_headers, json={"name": "HTTP plan"})
        assert created.status_code == 201, created.text
        data = created.json()["data"]
        plan_id = uuid.UUID(data["plan_id"])
        assert data["project_id"] == str(project) and data["plan_state"] == "ACTIVE"
        assert created.headers["etag"] == '"v0"'
        assert created.headers["location"] == f"{path}/{plan_id}"
        replay = client.post(path, headers=write_headers, json={"name": "HTTP plan"})
        assert replay.status_code == 201 and replay.json()["data"] == data
        assert client.post(path, headers=write_headers,
                           json={"name": "Collision"}).status_code == 409
        detail_response = client.get(f"{path}/{plan_id}", headers=headers)
        assert detail_response.status_code == 200, detail_response.text
        assert detail_response.json()["data"]["plan_id"] == str(plan_id)
        assert detail_response.json()["data"]["created_by"] == str(manager)
        assert detail_response.headers["etag"] == '"v0"'
        ids = []
        cursor = None
        while True:
            params = {"page_size": "1"}
            if cursor is not None:
                params["cursor"] = cursor
            response = client.get(path, params=params, headers=headers)
            assert response.status_code == 200, response.text
            page = response.json()["data"]
            assert len(page["items"]) == 1
            ids.append(uuid.UUID(page["items"][0]["plan_id"]))
            cursor = page["next_cursor"]
            if cursor is None:
                assert not page["has_more"]
                break
            assert page["has_more"] and len(ids) <= 5
        assert len(ids) == 5 and len(set(ids)) == 5 and plan_id in ids
        assert client.get(path, params={"page_size": "1", "cursor": "bad"},
                          headers=headers).status_code == 400
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert client.get(path, headers={**headers, "cookie": "plm_session="
                          + member_token.hex()}).status_code == 404
        assert client.get(path, headers={}).status_code == 401
        assert client.get(path, headers={**headers,
                          "origin": "https://evil.test"}).status_code == 403
        assert client.post(path, headers={**write_headers,
                           "x-csrf-token": (b"x" * 32).hex()},
                           json={"name": "Bad csrf"}).status_code == 403
    denied_detail, denied_list = create_windows_plan_read_routers(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=prior.DeniedLicense(), cursors=cursors)
    denied_create = create_windows_plan_create_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=prior.DeniedLicense(), audit=audit)
    with TestClient(create_app(plan_create_router=denied_create,
                               plan_read_router=denied_detail,
                               plan_list_router=denied_list),
                    base_url="https://plm.example.test") as denied:
        assert denied.get(path, headers=headers).status_code == 403
        assert denied.get(f"{path}/{plan_id}", headers=headers).status_code == 403
        assert denied.post(path, headers={**write_headers,
                           "idempotency-key": "l" * 16},
                           json={"name": "Denied"}).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.pln_plans WHERE project_id=%s",
                          (project,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "target_owner_module='plan'").fetchone()[0] == 3
    return 0


if __name__ == "__main__":
    prior.prior.main(on_created=on_created)
    print("PLAN_01_A04_P04_WINDOWS_COMPOSITION_PASS: real Session/ASGI/PG, "
          "write/read modes, replay, pages, isolation, revocation, License")
