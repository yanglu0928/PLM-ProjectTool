"""Win11 real HTTP/PostgreSQL proof for SOL-06 submit-review composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_structured_spec_review_submission_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_review_for_windows_submission",
    ROOT / "validation/sol-06-a14-p04-structured-spec-review/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, **_kwargs):
        from plm_assistant.modules.license.application.runtime_guard import (
            RuntimeLicenseError,
        )
        raise RuntimeLicenseError("EXPIRED")


def headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def on_http(
    *, port, runtime, project, other_project, manager, token, csrf,
    member_token, member_csrf, draft, audit, license_guard, documents,
    downloads, parse_results, evidence, approved_version, **_unused,
) -> None:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    dependencies = dict(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads, parse_results=parse_results)
    try:
        create_windows_structured_spec_review_submission_router(
            **{**dependencies, "parse_results": None})
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing current-source dependency mounted submit")
    router = create_windows_structured_spec_review_submission_router(
        **dependencies)
    path = (
        f"/api/v1/projects/{project}/structured-solution-specs/"
        f"{draft.structured_solution_spec_id}:submit-review")
    body = {
        "reviewer_ids": [str(manager)],
        "policy_ref": "STRUCTURED_SPEC_ALL_V1",
        "due_at": None,
        "submission_note": None,
    }
    key = "structured-submit-windows-0001"

    with TestClient(create_app(), base_url="https://plm.example.test") as closed:
        assert closed.post(
            path, headers=headers(token, csrf, key), json=body
        ).status_code == 404

    with TestClient(create_app(
            solution_structured_spec_review_submission_router=router),
            base_url="https://plm.example.test") as application:
        assert application.post(
            path.replace(str(project), str(other_project)),
            headers=headers(token, csrf, "structured-submit-other-0001"),
            json=body).status_code == 404
        assert application.post(
            path, headers=headers(
                member_token, member_csrf, "structured-submit-member-0001"),
            json=body).status_code == 404

        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin",
            dbname="postgres", autocommit=True,
        ) as database:
            database.execute("SET session_replication_role='replica'")
            database.execute(
                "UPDATE plm.evd_evidence_records SET "
                "eligibility_state='INELIGIBLE' "
                "WHERE evidence_id=%s", (evidence,))
        rejected = application.post(
            path, headers=headers(token, csrf, key), json=body)
        assert rejected.status_code == 422, rejected.text

        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin",
            dbname="postgres", autocommit=True,
        ) as database:
            database.execute("SET session_replication_role='replica'")
            database.execute(
                "UPDATE plm.evd_evidence_records SET "
                "eligibility_state='ELIGIBLE' "
                "WHERE evidence_id=%s", (evidence,))
        first = application.post(
            path, headers=headers(token, csrf, key), json=body)
        assert first.status_code == 201, first.text
        replay = application.post(
            path, headers=headers(token, csrf, key), json=body)
        assert replay.status_code == 201, replay.text
        assert replay.json()["data"] == first.json()["data"]
        assert replay.json()["trace_id"] != first.json()["trace_id"]
        assert replay.headers["x-trace-id"] == replay.json()["trace_id"]
        assert first.headers["etag"] == '"v1"'
        assert first.headers["cache-control"] == "no-store"
        data = first.json()["data"]
        assert data["spec_series_id"] == str(draft.spec_series_id)
        assert data["structured_solution_spec_id"] == str(
            draft.structured_solution_spec_id)
        assert data["state"] == "IN_REVIEW"

        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
        ) as database:
            alternate = database.execute(
                "SELECT user_id FROM plm.prj_project_members "
                "WHERE project_id=%s AND user_id<>%s AND state='ACTIVE' "
                "ORDER BY user_id LIMIT 1", (project, manager)).fetchone()
        assert alternate is not None
        changed = {**body, "reviewer_ids": [
            str(manager), str(alternate[0])]}
        assert application.post(
            path, headers=headers(token, csrf, key),
            json=changed).status_code == 409

    denied = create_windows_structured_spec_review_submission_router(
        **{**dependencies, "license_guard": DeniedLicense()})
    with TestClient(create_app(
            solution_structured_spec_review_submission_router=denied),
            base_url="https://plm.example.test") as application:
        assert application.post(
            path, headers=headers(
                token, csrf, "structured-submit-license-0001"),
            json=body).status_code == 403

    review_id = uuid.UUID(data["review_id"])
    round_id = uuid.UUID(data["review_round_id"])
    trace_id = uuid.UUID(first.json()["trace_id"])
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        state = database.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        assert state == ("IN_REVIEW", review_id, round_id), state
        counts = database.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s),"
            "(SELECT count(*) FROM plm.rvw_review_rounds "
            "WHERE review_round_id=%s),"
            "(SELECT count(*) FROM plm.sol_spec_review_state_results "
            "WHERE structured_solution_spec_id=%s AND event_type='START'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SPEC_SUBMIT_REVIEW'),"
            "(SELECT count(*) FROM plm.aud_events WHERE trace_id=%s "
            "AND action IN ('REVIEW_CREATED','REVIEW_STARTED'))",
            (review_id, round_id, draft.structured_solution_spec_id,
             trace_id)).fetchone()
        assert counts == (1, 1, 1, 1, 2), counts
        approved = database.execute(
            "SELECT structured_solution_spec_id FROM plm.sol_structured_specs "
            "WHERE spec_series_id=%s AND version_state='APPROVED'",
            (draft.spec_series_id,)).fetchall()
        assert approved == [(approved_version,)], approved

    print(
        "SOL_06_A14_P07_SUBMIT_WINDOWS_HTTP_PG_PASS: explicit write-mode "
        "composition, default/read exclusion, current-fact rejection then "
        "same-key success/replay, role/license/isolation, collision and one "
        "Review/Round/state receipt/platform receipt/Audit pair")


def after_specs(*, created: dict[str, object], **specs) -> None:
    prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.on_review(
            **review, on_submit=on_http))


if __name__ == "__main__":
    prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs: after_specs(
                    created=created, **specs))))
