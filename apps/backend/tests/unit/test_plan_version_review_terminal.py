from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanReviewReadinessDenied, PlanVersionReviewReadinessProof,
)
from plm_assistant.modules.plan.application.plan_version_review_terminal import (
    PlanReviewTerminalLock, PlanVersionReviewSubjectOwner,
)
from plm_assistant.modules.plan.application.plan_review_readiness import (
    snapshot_fingerprint,
)
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionSnapshotView,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
    ReviewRoundState, ReviewWithdrawalSnapshot,
)


NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def _setup():
    project, plan, version, actor, reviewer, trace = (uuid4() for _ in range(6))
    review_id, round_id = uuid4(), uuid4()
    snapshot = PlanVersionSnapshotView(
        version, plan, project, 1, "IN_REVIEW", actor, NOW, None,
        review_id, round_id, {"wbs_items": [{"id": "fixed"}]},
    )
    lock = PlanReviewTerminalLock(snapshot, version, None)
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, "PLN-02", version,
        "PLAN_VERSION_ALL_V1", "IN_REVIEW", round_id, 1,
    )
    progress = ReviewRoundProgress(round_id, NOW, (reviewer,))
    fingerprint = snapshot_fingerprint(snapshot)
    fixed = FixedReviewRoundSnapshot(
        identity, 1, version, actor, progress, (uuid4(),), 0,
        uuid4(), fingerprint, 1, NOW, (), uuid4(), NOW, None,
    )
    context = ReviewSubjectProofContext(b"s" * 32, trace)
    repo, reviewers, readiness, audit = Mock(), Mock(), Mock(), Mock()
    repo.lock_terminal_subject.return_value = lock
    repo.version_exists.return_value = True
    repo.consume_terminal.return_value = uuid4()
    reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(reviewer, project, "CUSTOMER_MANAGER"),)
    readiness.prove_terminal_in_transaction.return_value = PlanVersionReviewReadinessProof(
        project, plan, version, 1, fingerprint, NOW)
    owner = PlanVersionReviewSubjectOwner(
        repository=repo, reviewers=reviewers,
        readiness=readiness, audit=audit,
    )
    return locals()


def _transition(s, state):
    if state is ReviewRoundState.APPROVED:
        decision = ReviewDecisionSnapshot(
            uuid4(), s["round_id"], s["reviewer"],
            ReviewDecisionKind.APPROVE, NOW)
        after = s["progress"].record_decision(decision)
    elif state is ReviewRoundState.RETURNED:
        decision = ReviewDecisionSnapshot(
            uuid4(), s["round_id"], s["reviewer"],
            ReviewDecisionKind.RETURN, NOW, "Please revise")
        after = s["progress"].record_decision(decision)
    else:
        after = s["progress"].withdraw(
            ReviewWithdrawalSnapshot(s["actor"], NOW, "No longer required"))
    return ReviewSubjectTransition(
        s["reviewer"] if state is not ReviewRoundState.WITHDRAWN else s["actor"],
        s["trace"], s["fixed"], after, NOW, s["context"])


def test_approved_terminal_reproves_bound_current_snapshot_and_records_audit():
    s = _setup()
    transition = _transition(s, ReviewRoundState.APPROVED)
    s["owner"].require_transition_access_in_transaction(object(), transition)
    query = s["readiness"].prove_terminal_in_transaction.call_args.kwargs["query"]
    assert query.review_id == s["review_id"]
    assert query.review_round_id == s["round_id"]
    assert query.subject_fingerprint == s["fixed"].subject_fingerprint
    s["owner"].consume_terminal_in_transaction(object(), transition)
    assert s["repo"].consume_terminal.call_args.kwargs == {
        "before": s["lock"], "transition": transition,
        "version_state": "APPROVED", "event_type": "APPROVED",
    }
    assert s["audit"].append.call_args.args[1].action == "PLAN_VERSION_REVIEW_APPROVED"


@pytest.mark.parametrize(("state", "expected_state", "event_type"), [
    (ReviewRoundState.RETURNED, "RETURNED", "RETURNED"),
    (ReviewRoundState.WITHDRAWN, "RETURNED", "WITHDRAWN"),
])
def test_nonapproval_terminal_preserves_pointer_and_does_not_reprove_sources(
        state, expected_state, event_type):
    s = _setup()
    transition = _transition(s, state)
    s["owner"].require_transition_access_in_transaction(object(), transition)
    s["readiness"].prove_terminal_in_transaction.assert_not_called()
    s["owner"].consume_terminal_in_transaction(object(), transition)
    kwargs = s["repo"].consume_terminal.call_args.kwargs
    assert kwargs["version_state"] == expected_state
    assert kwargs["event_type"] == event_type


def test_terminal_owner_rejects_reviewer_revocation_and_content_drift():
    s = _setup()
    transition = _transition(s, ReviewRoundState.APPROVED)
    s["reviewers"].qualify_in_transaction.side_effect = ReviewReviewerEligibilityError()
    with pytest.raises(ReviewSubjectAccessDenied):
        s["owner"].require_transition_access_in_transaction(object(), transition)
    s["repo"].consume_terminal.assert_not_called()

    s = _setup()
    transition = _transition(s, ReviewRoundState.APPROVED)
    drifted = replace(s["snapshot"], snapshot={"wbs_items": [{"id": "changed"}]})
    s["repo"].lock_terminal_subject.return_value = PlanReviewTerminalLock(
        drifted, s["version"], None)
    with pytest.raises(ReviewSubjectAccessDenied):
        s["owner"].require_transition_access_in_transaction(object(), transition)
    s["readiness"].prove_terminal_in_transaction.assert_not_called()


def test_terminal_callback_requires_registry_exact_plan_version_identity():
    s = _setup()
    transition = _transition(s, ReviewRoundState.RETURNED)
    bad_identity = replace(transition.before.review, subject_id=uuid4())
    bad_before = replace(transition.before, review=bad_identity)
    bad_transition = replace(transition, before=bad_before)
    with pytest.raises((ReviewSubjectAccessDenied, ValueError)):
        s["owner"].require_transition_access_in_transaction(object(), bad_transition)
