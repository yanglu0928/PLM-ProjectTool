"""Win11 real HTTP/PostgreSQL proof for the SOL-06 REVIEW_GET composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_read_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_terminal_for_review_get_windows",
    ROOT / "validation/sol-06-a15-p02-structured-spec-review-terminal-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _headers(token: bytes) -> dict[str, str]:
    return {"cookie": "plm_session=" + token.hex()}


def _read_router(*, runtime, license_guard, audit, documents, downloads,
                 parse_results, **_unused):
    return create_windows_project_review_read_router(
        runtime, origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit, documents=documents,
        downloads=downloads, parse_results=parse_results)


def _review_ids(*, port, draft, **_unused) -> tuple[uuid.UUID, uuid.UUID]:
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        result = database.execute(
            "SELECT review_ref,review_round_ref FROM plm.sol_structured_specs "
            "WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
    assert result and all(isinstance(value, uuid.UUID) for value in result)
    return result


def _audit_count(port: int) -> int:
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        return database.execute(
            "SELECT count(*) FROM plm.aud_events").fetchone()[0]


def _active_read(case: str, **context) -> tuple[object, str]:
    project, other_project = context["project"], context["other_project"]
    token, member_token = context["token"], context["member_token"]
    draft, port = context["draft"], context["port"]
    review_id, round_id = _review_ids(**context)
    router = _read_router(**context)
    path = f"/api/v1/projects/{project}/reviews/{review_id}"
    before = _audit_count(port)

    with TestClient(
            create_app(), base_url="https://plm.example.test") as closed:
        assert closed.get(path, headers=_headers(token)).status_code == 404
    with TestClient(
            create_app(review_read_router=router),
            base_url="https://plm.example.test") as application:
        assert application.get(path).status_code == 401
        assert application.get(path, headers=_headers(b"z" * 32)).status_code == 401
        assert application.get(
            path + "?round=latest", headers=_headers(token)).status_code == 400
        assert application.get(
            path.replace(str(review_id), str(review_id).upper()),
            headers=_headers(token)).status_code == 422
        assert application.get(
            path.replace(str(project), str(other_project)),
            headers=_headers(token)).status_code == 404

        manager = application.get(path, headers=_headers(token))
        member = application.get(path, headers=_headers(member_token))
        assert manager.status_code == member.status_code == 200
        assert manager.json()["data"] == member.json()["data"]
        assert manager.json()["trace_id"] != member.json()["trace_id"]
        assert manager.headers["etag"] == '"v1"'
        assert manager.headers["cache-control"] == "no-store"
        data = manager.json()["data"]
        assert set(data) == {
            "review_id", "project_id", "subject_ref", "policy_code",
            "state", "active_round", "etag",
        }
        assert data["review_id"] == str(review_id)
        assert data["project_id"] == str(project)
        assert data["subject_ref"] == {
            "resource_type": "SOL-06",
            "resource_id": str(draft.spec_series_id),
        }
        assert data["policy_code"] == "STRUCTURED_SPEC_ALL_V1"
        assert data["state"] == "IN_REVIEW" and data["etag"] == '"v1"'
        active = data["active_round"]
        assert active["review_round_id"] == str(round_id)
        assert active["subject_version_ref"] == str(
            draft.structured_solution_spec_id)
        assert active["state"] == "IN_REVIEW"
        assert active["round_etag"] == '"v0"'
        assert len(active["assignments"]) == 1
        assert active["assignments"][0]["reviewer_id"] == str(
            context["manager"])
        assert active["assignments"][0]["state"] == "PENDING"
        assert active["assignments"][0]["decision"] is None

    denied = _read_router(
        **{**context, "license_guard": prior.prior.DeniedLicense()})
    with TestClient(
            create_app(review_read_router=denied),
            base_url="https://plm.example.test") as application:
        assert application.get(path, headers=_headers(token)).status_code == 403
    assert _audit_count(port) == before
    print(
        f"SOL_06_A15_P04_ACTIVE_{case}_REVIEW_GET_HTTP_PG_PASS: default "
        "closed, current PROJECT member/series/fixed-version authorization, "
        "isolation/license/session/query denial and zero read writes")
    return router, path


def _terminal_read(case: str, router, path: str, **context) -> None:
    before = _audit_count(context["port"])
    with TestClient(
            create_app(review_read_router=router),
            base_url="https://plm.example.test") as application:
        response = application.get(path, headers=_headers(context["token"]))
        assert response.status_code == 200, response.text
        expected = "APPROVED" if case == "APPROVE" else "RETURNED"
        assert response.json()["data"]["state"] == expected
        assert response.json()["data"]["active_round"] is None
        assert response.json()["data"]["etag"] == '"v2"'
        assert response.headers["etag"] == '"v2"'
    assert _audit_count(context["port"]) == before
    print(
        f"SOL_06_A15_P04_TERMINAL_{case}_REVIEW_GET_HTTP_PG_PASS: exact "
        "terminal Review identity with null active_round, current ETag and "
        "zero read writes")


def _after_submit(case: str, **context) -> None:
    prior.prior.on_http(**context)
    router, path = _active_read(case, **context)
    prior._terminal(case, **context)
    _terminal_read(case, router, path, **context)


def _after_specs(case: str, *, created: dict[str, object], **specs) -> None:
    prior.prior.prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.prior.prior.on_review(
            **review, on_submit=lambda **submit: _after_submit(case, **submit)))


def _run(case: str) -> None:
    prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                _after_specs(case, created=created, **specs))))


if __name__ == "__main__":
    _run("APPROVE")
    _run("RETURN")
