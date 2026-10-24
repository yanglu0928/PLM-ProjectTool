"""Outline submit service controls identity, role, receipt and Review kernel."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission, SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
)
from plm_assistant.modules.solution.application.outline_submit_review import (
    OutlineReviewSubmissionError, OutlineReviewSubmissionService,
    SubmitOutlineReview,
)


NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


class Transaction:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        type(self).commits += 1


@pytest.fixture
def setup():
    actor, project, outline, version, review, round_id = (
        uuid4() for _ in range(6))
    reviewer_a, reviewer_b, trace = uuid4(), uuid4(), uuid4()
    reviewer_ids = tuple(sorted((reviewer_a, reviewer_b), key=str))
    command = SubmitOutlineReview(
        b"s" * 32, b"c" * 32, trace, project, outline, version,
        (reviewer_b, reviewer_a), "SOLUTION_OUTLINE_ALL_V1", str(uuid4()))
    result = SubmittedProjectReviewRef(
        review, round_id, project, "SOL-03", outline, version,
        "SOLUTION_OUTLINE_ALL_V1", reviewer_ids, actor, NOW)
    access, guard, authorization, reviewers, receipts, replays, reviews, subjects = (
        Mock() for _ in range(8))
    access.authenticated_user.return_value = actor
    authorization.require_in_transaction.return_value = AuthorizedProjectAction(
        actor, project, "SOL_OUTLINE_VERSION_SUBMIT_REVIEW", "PROJECT_MANAGER")
    receipts.reserve.return_value = None
    reviews.submit_in_transaction.return_value = result
    reviews.is_retryable_deadlock.return_value = False
    replays.is_retryable_deadlock.return_value = False
    Transaction.commits = 0
    service = OutlineReviewSubmissionService(
        unit_of_work=Transaction, access=access, license_guard=guard,
        authorization=authorization, reviewers=reviewers,
        receipts=receipts, replay_repository=replays, reviews=reviews,
        subjects=subjects, clock=lambda: NOW)
    return locals()


def test_submission_binds_exact_outline_and_current_proof(setup):
    s = setup
    assert s["service"].submit(s["command"]) == s["result"]
    assert Transaction.commits == 1
    assert s["authorization"].require_in_transaction.call_args.kwargs[
        "operation"] == "SOL_OUTLINE_VERSION_SUBMIT_REVIEW"
    fields = s["reviews"].submit_in_transaction.call_args.kwargs
    assert fields["subject_type"] == "SOL-03"
    assert (fields["subject_id"], fields["subject_version_id"]) == (
        s["outline"], s["version"])
    assert fields["reviewer_ids"] == s["reviewer_ids"]
    assert type(fields["proof_context"]) is ReviewSubjectProofContext
    assert fields["proof_context"].session_token == b"s" * 32
    scope = s["receipts"].reserve.call_args.kwargs["scope"]
    assert scope.operation == "V1_SOL_OUTLINE_VERSION_SUBMIT_REVIEW"
    assert s["receipts"].complete.call_args.kwargs["result"] == (
        IdempotencyResult("V1_SOL_OUTLINE_REVIEW_SUBMISSION", s["round_id"], 201))


def test_replay_uses_fixed_round_and_rechecks_owner_access(setup):
    s = setup
    s["receipts"].reserve.return_value = IdempotencyResult(
        "V1_SOL_OUTLINE_REVIEW_SUBMISSION", s["round_id"], 201)
    identity = ReviewIdentitySnapshot(
        s["review"], "PROJECT", s["project"], "SOL-03", s["outline"],
        "SOLUTION_OUTLINE_ALL_V1", "IN_REVIEW", s["round_id"], 1)
    s["replays"].get_project_submission.return_value = (
        PersistedProjectReviewSubmission(identity, s["result"]))
    assert s["service"].submit(s["command"]) == s["result"]
    s["subjects"].require_start_replay_access_in_transaction.assert_called_once()
    s["reviews"].submit_in_transaction.assert_not_called()
    assert Transaction.commits == 0
    s["subjects"].require_start_replay_access_in_transaction.side_effect = (
        ReviewSubjectAccessDenied())
    with pytest.raises(OutlineReviewSubmissionError) as error:
        s["service"].submit(s["command"])
    assert error.value.code == "BUSINESS_REVIEW_NOT_ELIGIBLE"


@pytest.mark.parametrize("field,value", [
    ("reviewer_ids", ()),
    ("policy_ref", "OTHER"),
    ("session_token", b"short"),
    ("outline_version_id", None),
])
def test_invalid_command_fails_before_side_effect(setup, field, value):
    s = setup
    with pytest.raises(OutlineReviewSubmissionError) as error:
        s["service"].submit(replace(s["command"], **{field: value}))
    assert error.value.code == "VALIDATION_FAILED"
    s["reviews"].submit_in_transaction.assert_not_called()
    assert Transaction.commits == 0


def test_license_role_and_wrong_review_identity_fail_closed(setup):
    s = setup
    s["guard"].require_valid.side_effect = RuntimeLicenseError("EXPIRED")
    with pytest.raises(OutlineReviewSubmissionError) as error:
        s["service"].submit(s["command"])
    assert error.value.code == "LICENSE_OPERATION_DENIED"
    s["guard"].require_valid.side_effect = None
    s["authorization"].require_in_transaction.return_value = (
        AuthorizedProjectAction(
            s["actor"], s["project"],
            "SOL_OUTLINE_VERSION_SUBMIT_REVIEW", "IMPLEMENTATION_MEMBER"))
    with pytest.raises(OutlineReviewSubmissionError) as error:
        s["service"].submit(s["command"])
    assert error.value.code == "RESOURCE_NOT_FOUND"
    s["authorization"].require_in_transaction.return_value = (
        AuthorizedProjectAction(
            s["actor"], s["project"],
            "SOL_OUTLINE_VERSION_SUBMIT_REVIEW", "PROJECT_MANAGER"))
    s["reviews"].submit_in_transaction.return_value = replace(
        s["result"], subject_id=uuid4())
    with pytest.raises(OutlineReviewSubmissionError) as error:
        s["service"].submit(s["command"])
    assert error.value.code == "SYSTEM_UNAVAILABLE"
    assert Transaction.commits == 0
    assert b"s" * 32 not in repr(s["command"]).encode()
