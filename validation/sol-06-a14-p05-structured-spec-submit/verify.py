"""Win11/PG18 proof for atomic SOL-06 Review submission."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.project_submission_repository import (
    SqlAlchemyProjectReviewSubmissionRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.solution.application.structured_spec_submit_review import (
    StructuredSpecReviewSubmissionError,
    StructuredSpecReviewSubmissionService,
    SubmitStructuredSpecReview,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_review_for_submission",
    ROOT / "validation/sol-06-a14-p04-structured-spec-review/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("injected SOL-06 submission audit failure")


def on_submit(
    *, port, runtime, project, manager, token, csrf, draft, audit,
    license_guard, access, authorization, reviewers, owner, identity,
    approved_version,
) -> None:
    receipts = SqlAlchemyIdempotencyReceipts()
    replays = SqlAlchemyProjectReviewSubmissionRepository()

    def service(review_audit):
        return StructuredSpecReviewSubmissionService(
            unit_of_work=runtime.unit_of_work,
            access=access, license_guard=license_guard,
            authorization=authorization, reviewers=reviewers,
            receipts=receipts, replay_repository=replays,
            identity=identity,
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=review_audit, subjects=owner),
            subjects=owner,
        )

    key = str(uuid.uuid4())
    command = SubmitStructuredSpecReview(
        token, csrf, uuid.uuid4(), project,
        draft.structured_solution_spec_id, (manager,),
        "STRUCTURED_SPEC_ALL_V1", key)

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        before = db.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_reviews WHERE subject_id=%s),"
            "(SELECT count(*) FROM plm.rvw_review_rounds r JOIN "
            "plm.rvw_reviews v ON v.review_id=r.review_id "
            "WHERE v.subject_id=%s),"
            "(SELECT count(*) FROM plm.sol_spec_review_state_results "
            "WHERE spec_series_id=%s),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SPEC_SUBMIT_REVIEW')",
            (draft.spec_series_id,) * 3).fetchone()

    try:
        service(FailingAudit()).submit(command)
    except StructuredSpecReviewSubmissionError as error:
        assert error.code == "SYSTEM_UNAVAILABLE", error.code
    else:
        raise AssertionError("injected Audit failure must fail closed")

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        after_failure = db.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_reviews WHERE subject_id=%s),"
            "(SELECT count(*) FROM plm.rvw_review_rounds r JOIN "
            "plm.rvw_reviews v ON v.review_id=r.review_id "
            "WHERE v.subject_id=%s),"
            "(SELECT count(*) FROM plm.sol_spec_review_state_results "
            "WHERE spec_series_id=%s),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SPEC_SUBMIT_REVIEW')",
            (draft.spec_series_id,) * 3).fetchone()
        state_after_failure = db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
    assert after_failure == before, (before, after_failure)
    assert state_after_failure == ("DRAFT", None, None), state_after_failure

    live = service(audit)
    first = live.submit(command)
    replay = live.submit(command)
    assert first == replay
    assert first.subject_type == "SOL-06"
    assert first.subject_id == draft.spec_series_id
    assert first.subject_version_id == draft.structured_solution_spec_id
    assert first.policy_code == "STRUCTURED_SPEC_ALL_V1"
    assert first.reviewer_ids == (manager,)

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        alternate = db.execute(
            "SELECT user_id FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id<>%s AND state='ACTIVE' "
            "ORDER BY user_id LIMIT 1",
            (project, manager)).fetchone()
    assert alternate is not None
    collision = SubmitStructuredSpecReview(
        token, csrf, uuid.uuid4(), project,
        draft.structured_solution_spec_id,
        tuple(sorted((manager, alternate[0]), key=str)),
        "STRUCTURED_SPEC_ALL_V1", key)
    try:
        live.submit(collision)
    except StructuredSpecReviewSubmissionError as error:
        assert error.code == "CONFLICT_IDEMPOTENCY", error.code
    else:
        raise AssertionError("changed payload must conflict with original key")

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        state = db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        assert state == ("IN_REVIEW", first.review_id, first.round_id), state
        counts = db.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s),"
            "(SELECT count(*) FROM plm.rvw_review_rounds "
            "WHERE review_round_id=%s),"
            "(SELECT count(*) FROM plm.sol_spec_review_state_results "
            "WHERE structured_solution_spec_id=%s AND review_id=%s "
            "AND review_round_id=%s AND event_type='START'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SPEC_SUBMIT_REVIEW'),"
            "(SELECT count(*) FROM plm.aud_events WHERE trace_id=%s "
            "AND action IN ('REVIEW_CREATED','REVIEW_STARTED'))",
            (first.review_id, first.round_id,
             draft.structured_solution_spec_id, first.review_id,
             first.round_id, command.trace_id)).fetchone()
        assert counts == (1, 1, 1, before[3] + 1, 2), counts
        approved = db.execute(
            "SELECT structured_solution_spec_id FROM plm.sol_structured_specs "
            "WHERE spec_series_id=%s AND version_state='APPROVED'",
            (draft.spec_series_id,)).fetchall()
        assert approved == [(approved_version,)], approved

    print(
        "SOL_06_A14_P05_SUBMIT_PG_PASS: immutable series resolution, "
        "same-transaction current-fact Review create/start, persistent replay, "
        "payload collision, Audit rollback and approved-pointer preservation")


def after_specs(*, created: dict[str, object], **specs) -> None:
    prior.prior.on_trace(
        **specs, csrf=created["csrf"], audit=created["audit"],
        license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"],
        on_review=lambda **review: prior.on_review(
            **review, on_submit=on_submit))


if __name__ == "__main__":
    prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs: after_specs(
                    created=created, **specs))))
