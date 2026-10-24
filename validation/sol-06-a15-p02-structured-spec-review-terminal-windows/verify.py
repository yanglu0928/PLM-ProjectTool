"""Win11 real HTTP/PostgreSQL proof for SOL-06 terminal Review composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_submit_for_terminal_windows",
    ROOT / "validation/sol-06-a14-p07-structured-spec-submit-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _terminal(
    case: str, *, port, runtime, project, other_project, manager, token, csrf,
    member_token, member_csrf, draft, audit, license_guard, documents,
    downloads, parse_results, evidence, approved_version, **_unused,
) -> None:
    assert case in {"APPROVE", "RETURN"}
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        review_id, round_id = database.execute(
            "SELECT review_ref,review_round_ref FROM plm.sol_structured_specs "
            "WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
    assert isinstance(review_id, uuid.UUID) and isinstance(round_id, uuid.UUID)

    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    dependencies = dict(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    router = create_windows_project_review_router(**dependencies)
    path = (
        f"/api/v1/projects/{project}/reviews/{review_id}/rounds/"
        f"{round_id}:decide")
    key = f"structured-terminal-{case.lower()}-0001"
    body = {
        "decision": case,
        "comment": (None if case == "APPROVE" else "Please correct the design."),
    }

    if case == "APPROVE":
        with TestClient(
                create_app(), base_url="https://plm.example.test") as closed:
            assert closed.post(
                path, headers=prior.headers(token, csrf, key),
                json=body).status_code == 404
        with TestClient(
                create_app(review_command_router=router),
                base_url="https://plm.example.test") as application:
            assert application.post(
                path.replace(str(project), str(other_project)),
                headers=prior.headers(
                    token, csrf, "structured-terminal-other-0001"),
                json=body).status_code == 404
            assert application.post(
                path, headers=prior.headers(
                    member_token, member_csrf,
                    "structured-terminal-member-0001"),
                json=body).status_code == 404

        denied = create_windows_project_review_router(
            **{**dependencies, "license_guard": prior.DeniedLicense()})
        with TestClient(
                create_app(review_command_router=denied),
                base_url="https://plm.example.test") as application:
            assert application.post(
                path, headers=prior.headers(
                    token, csrf, "structured-terminal-license-0001"),
                json=body).status_code == 403

        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin",
            dbname="postgres", autocommit=True,
        ) as database:
            database.execute("SET session_replication_role='replica'")
            database.execute(
                "UPDATE plm.evd_evidence_records SET "
                "eligibility_state='INELIGIBLE' WHERE evidence_id=%s",
                (evidence,))
        with TestClient(
                create_app(review_command_router=router),
                base_url="https://plm.example.test") as application:
            rejected = application.post(
                path, headers=prior.headers(token, csrf, key), json=body)
            assert rejected.status_code == 404, rejected.text
        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin",
            dbname="postgres", autocommit=True,
        ) as database:
            database.execute("SET session_replication_role='replica'")
            database.execute(
                "UPDATE plm.evd_evidence_records SET "
                "eligibility_state='ELIGIBLE' WHERE evidence_id=%s",
                (evidence,))
            assert database.execute(
                "SELECT count(*) FROM plm.rvw_review_decisions "
                "WHERE review_round_id=%s", (round_id,)).fetchone()[0] == 0

    with TestClient(
            create_app(review_command_router=router),
            base_url="https://plm.example.test") as application:
        if case == "RETURN":
            invalid = application.post(
                path, headers=prior.headers(
                    token, csrf, "structured-terminal-empty-return-0001"),
                json={"decision": "RETURN", "comment": "  "})
            assert invalid.status_code == 422, invalid.text
        first = application.post(
            path, headers=prior.headers(token, csrf, key), json=body)
        assert first.status_code == 200, first.text
        replay = application.post(
            path, headers=prior.headers(token, csrf, key), json=body)
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == first.json()["data"]
        assert replay.json()["trace_id"] != first.json()["trace_id"]
        assert first.headers["etag"] == '"v2"'
        assert first.headers["cache-control"] == "no-store"
        data = first.json()["data"]
        assert data["review_id"] == str(review_id)
        assert data["review_round_id"] == str(round_id)
        assert data["subject_version_ref"] == str(
            draft.structured_solution_spec_id)
        assert data["actor_id"] == str(manager)
        assert data["decision"] == case
        assert data["assignment_state"] == "DECIDED"
        assert data["state"] == ("APPROVED" if case == "APPROVE" else "RETURNED")
        assert data["round_etag"] == '"v1"'
        collision = application.post(
            path, headers=prior.headers(token, csrf, key),
            json={**body, "comment": "different"})
        assert collision.status_code == 409, collision.text

    event_id = uuid.UUID(data["event_id"])
    trace_id = uuid.UUID(first.json()["trace_id"])
    expected_state = "APPROVED" if case == "APPROVE" else "RETURNED"
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        state = database.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        assert state == (expected_state, review_id, round_id), state
        review_state = database.execute(
            "SELECT r.review_state,rr.round_state,rr.lock_version "
            "FROM plm.rvw_reviews r JOIN plm.rvw_review_rounds rr "
            "ON rr.review_id=r.review_id WHERE r.review_id=%s "
            "AND rr.review_round_id=%s", (review_id, round_id)).fetchone()
        assert review_state == (expected_state, expected_state, 1), review_state
        decision = database.execute(
            "SELECT decision,comment,reviewer_id FROM plm.rvw_review_decisions "
            "WHERE review_round_id=%s", (round_id,)).fetchall()
        assert decision == [(case, body["comment"], manager)], decision
        counts = database.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.sol_spec_review_state_results WHERE "
            "structured_solution_spec_id=%s AND event_type=%s),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_REVIEW_DECIDE' AND result_ref_id=%s AND "
            "result_ref_type='V1_REVIEW_TRANSITION'),"
            "(SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND "
            "action IN ('REVIEW_DECISION_RECORDED',%s))",
            (draft.structured_solution_spec_id, expected_state, event_id,
             trace_id, f"STRUCTURED_SPEC_VERSION_{expected_state}"),
        ).fetchone()
        assert counts == (1, 1, 2), counts
        approved = database.execute(
            "SELECT structured_solution_spec_id FROM plm.sol_structured_specs "
            "WHERE spec_series_id=%s AND version_state='APPROVED'",
            (draft.spec_series_id,)).fetchall()
        expected_approved = (
            [(draft.structured_solution_spec_id,)]
            if case == "APPROVE" else [(approved_version,)])
        assert approved == expected_approved, approved
    print(
        f"SOL_06_A15_P02_TERMINAL_{case}_HTTP_PG_PASS: unified Windows Review "
        "router, assigned reviewer, current-fact/license/isolation denial, "
        "exact replay/collision and atomic Review/SOL-06/Audit/receipt")


def _after_submit(case: str, **context) -> None:
    prior.on_http(**context)
    _terminal(case, **context)


def _after_specs(case: str, *, created: dict[str, object], **specs) -> None:
    prior.prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.prior.on_review(
            **review, on_submit=lambda **submit: _after_submit(case, **submit)))


def _run(case: str) -> None:
    prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                _after_specs(case, created=created, **specs))))


if __name__ == "__main__":
    _run("APPROVE")
    _run("RETURN")
