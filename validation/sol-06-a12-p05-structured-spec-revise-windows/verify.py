"""Disposable Win11 ASGI/PG18 proof for SOL-06 Windows REVISE composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_structured_spec_revise_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_windows_create_for_revision",
    ROOT / "validation/sol-06-a09-p05-structured-spec-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_revision(*, app, create_router, revise_router, project, other_project,
                token, csrf, member_token, member_csrf, body, first, port,
                **_unused):
    path = (
        f"/api/v1/projects/{project}/structured-solution-specs/"
        f"{first['structured_solution_spec_id']}:revise")
    with TestClient(create_app(
            solution_structured_spec_create_router=create_router),
            base_url="https://plm.example.test") as create_only:
        assert create_only.post(
            path, headers=prior.headers(token, csrf, "closed-revise-001"),
            json=body).status_code == 404
    assert revise_router is not None
    revised_body = {
        **body, "payload": {**body["payload"],
                            "scope": "parts and documents"},
    }
    first_revision = app.post(
        path, headers=prior.headers(token, csrf, "revise-key-00001"),
        json=revised_body)
    assert first_revision.status_code == 201, first_revision.text
    second = first_revision.json()["data"]
    assert second["version_no"] == 2
    assert second["version_state"] == "DRAFT"
    assert second["spec_series_id"] == first["spec_series_id"]
    assert second["supersedes_version_ref"] == first["structured_solution_spec_id"]
    assert second["payload"] == revised_body["payload"]
    assert first_revision.headers["location"].endswith(
        second["structured_solution_spec_id"])
    replay = app.post(
        path, headers=prior.headers(token, csrf, "revise-key-00001"),
        json=revised_body)
    assert replay.status_code == 201
    assert replay.json()["data"] == second
    assert replay.json()["trace_id"] != first_revision.json()["trace_id"]
    assert app.post(
        path, headers=prior.headers(token, csrf, "revise-key-00001"),
        json={**revised_body, "payload": {
            **revised_body["payload"], "scope": "changed"}}).status_code == 409
    assert app.post(
        path, headers=prior.headers(token, csrf, "stale-key-000001"),
        json=revised_body).json()["error"]["code"] == "CONFLICT_VERSION"
    assert app.post(
        path.replace(str(project), str(other_project)),
        headers=prior.headers(token, csrf, "other-key-0000001"),
        json=revised_body).status_code == 404
    assert app.post(
        path, headers=prior.headers(token, b"x" * 32, "csrf-key-00000001"),
        json=revised_body).status_code == 403
    assert app.post(
        path + "?force=true",
        headers=prior.headers(token, csrf, "query-key-0000001"),
        json=revised_body).status_code == 400
    assert app.post(
        path, headers=prior.headers(token, csrf, "artifact-key-0001"),
        json={**revised_body,
              "artifact_ids": [str(uuid.uuid4())]}).status_code == 422
    member_path = (
        f"/api/v1/projects/{project}/structured-solution-specs/"
        f"{second['structured_solution_spec_id']}:revise")
    member = app.post(
        member_path,
        headers=prior.headers(member_token, member_csrf, "member-revise-001"),
        json=revised_body)
    assert member.status_code == 201, member.text
    third = member.json()["data"]
    assert third["version_no"] == 3
    assert third["supersedes_version_ref"] == second["structured_solution_spec_id"]
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_structured_specs WHERE spec_series_id=%s",
            (uuid.UUID(first["spec_series_id"]),)).fetchone()[0] == 3
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_STRUCTURED_SPEC_REVISE'").fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_STRUCTURED_SPEC_REVISED'").fetchone()[0] == 2
    print("SOL_06_A12_P05_WINDOWS_REVISION_HTTP_PG_PASS: explicit write-only "
          "composition, real auth/source/PG v1-v3, replay, conflicts and rejects")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **created: prior.on_http(
            **created,
            revise_router_factory=create_windows_structured_spec_revise_router,
            on_revise=on_revision)))
