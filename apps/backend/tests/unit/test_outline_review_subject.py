"""SOL-03 Outline Review has exact identity and fail-closed customer approval."""

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import CreatedReviewRef
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.solution.application.outline_review_readiness import (
    OutlineReviewReadinessError, OutlineReviewReadinessProof,
)
from plm_assistant.modules.solution.application.outline_review_subject import (
    OutlineReviewLock, OutlineReviewSubjectOwner,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineVersionValidationFacts,
)


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
FACTS = OutlineVersionValidationFacts("PASS", "PASS", "PASS")


@pytest.fixture
def setup():
    project, outline, version, actor, reviewer, trace = (uuid4() for _ in range(6))
    review_id, round_id = uuid4(), uuid4()
    fixed = OutlineVersionHistoryView(
        version, outline, project, 1, "DRAFT", b"x" * 32,
        (uuid4(),), (), (), (), (), None, None, None, actor, NOW)
    lock = OutlineReviewLock(fixed, version, None)
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, "SOL-03", outline,
        "SOLUTION_OUTLINE_ALL_V1", "DRAFT", None, 0)
    request = ReviewSubjectStartRequest(
        actor, identity, round_id, version, (reviewer,),
        ReviewSubjectProofContext(b"s" * 32, trace))
    repo, reviewers, readiness, audit = Mock(), Mock(), Mock(), Mock()
    repo.lock_subject.return_value = lock
    repo.outline_exists.return_value = True
    repo.version_exists.return_value = True
    repo.consume_terminal.return_value = uuid4()
    repo.assert_terminal_consumed = Mock(return_value=uuid4())
    reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(reviewer, project, "CUSTOMER_MANAGER"),)
    readiness.prove.return_value = OutlineReviewReadinessProof(
        fixed, FACTS, NOW, fixed.content_fingerprint)
    owner = OutlineReviewSubjectOwner(
        repository=repo, reviewers=reviewers, readiness=readiness, audit=audit)
    return SimpleNamespace(**locals())


def test_create_only_latest_draft_and_history_replay(setup):
    s = setup
    result = s.owner.authorize_create(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="SOL-03", subject_id=s.outline,
        subject_version_id=s.version)
    assert result.policy_code == "SOLUTION_OUTLINE_ALL_V1"
    created = CreatedReviewRef(
        s.review_id, s.project, "SOL-03", s.outline,
        "SOLUTION_OUTLINE_ALL_V1", s.actor, NOW)
    assert s.owner.authorize_replay(object(), user_id=s.actor, review=created)
    s.repo.lock_subject.return_value = replace(s.lock, latest_version_id=uuid4())
    assert s.owner.authorize_create(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="SOL-03", subject_id=s.outline,
        subject_version_id=s.version) is None


def test_start_pins_exact_version_and_customer_reviewer(setup):
    s = setup
    prepared = s.owner.prepare_start_in_transaction(object(), s.request)
    assert prepared.content_fingerprint == s.fixed.content_fingerprint
    assert prepared.qualified_reviewer_ids == (s.reviewer,)
    query = s.readiness.prove.call_args.kwargs["query"]
    assert (query.project_id, query.solution_outline_id,
            query.solution_outline_version_id) == (
                s.project, s.outline, s.version)
    s.owner.finalize_start_in_transaction(object(), s.request)
    assert s.repo.bind_start.call_args.kwargs["before"] == s.lock


@pytest.mark.parametrize("failure", ["context", "non_customer", "revoked", "fact"])
def test_start_fails_closed(failure, setup):
    s = setup
    request = s.request
    if failure == "context":
        request = replace(request, proof_context=None)
    elif failure == "non_customer":
        s.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(s.reviewer, s.project, "IMPLEMENTATION_MEMBER"),)
    elif failure == "revoked":
        s.reviewers.qualify_in_transaction.side_effect = ReviewReviewerEligibilityError()
    else:
        s.readiness.prove.side_effect = OutlineReviewReadinessError()
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(object(), request)
    s.repo.bind_start.assert_not_called()


def _approval(s):
    active = replace(s.lock, version=replace(
        s.fixed, version_state="IN_REVIEW", review_ref=s.review_id,
        review_round_ref=s.round_id))
    s.repo.lock_subject.return_value = active
    s.readiness.prove.return_value = OutlineReviewReadinessProof(
        active.version, FACTS, NOW, active.version.content_fingerprint,
        "IN_REVIEW")
    progress = ReviewRoundProgress(s.round_id, NOW, (s.reviewer,))
    identity = replace(s.identity, state="IN_REVIEW",
                       active_round_id=s.round_id, lock_version=1)
    before = FixedReviewRoundSnapshot(
        identity, 1, s.version, s.actor, progress, (uuid4(),), 0,
        uuid4(), s.fixed.content_fingerprint, 1, NOW, (), uuid4(), NOW, None)
    decision = ReviewDecisionSnapshot(
        uuid4(), s.round_id, s.reviewer, ReviewDecisionKind.APPROVE, NOW, None)
    return ReviewSubjectTransition(
        s.reviewer, s.trace, before, progress.record_decision(decision),
        NOW, s.request.proof_context), active


def test_approval_reproves_current_and_consumes_terminal(setup):
    s = setup
    transition, active = _approval(s)
    s.owner.require_transition_access_in_transaction(object(), transition)
    assert s.readiness.prove.call_args.kwargs["required_state"] == "IN_REVIEW"
    s.owner.consume_terminal_in_transaction(object(), transition)
    assert s.repo.consume_terminal.call_args.kwargs == dict(
        before=active, transition=transition, version_state="APPROVED")
    event = s.audit.append.call_args.args[1]
    assert event.action == "SOLUTION_OUTLINE_VERSION_APPROVED"
    assert event.target_object_id == s.outline
    s.owner.assert_terminal_consumed_in_transaction(object(), transition)


@pytest.mark.parametrize("failure", [
    "stale_fingerprint", "wrong_round", "non_customer", "missing_context",
    "source_unavailable",
])
def test_approval_rejects_binding_qualification_and_source_drift(setup, failure):
    s = setup
    transition, active = _approval(s)
    if failure == "stale_fingerprint":
        s.repo.lock_subject.return_value = replace(
            active, version=replace(active.version, content_fingerprint=b"z" * 32))
    elif failure == "wrong_round":
        s.repo.lock_subject.return_value = replace(
            active, version=replace(active.version, review_round_ref=uuid4()))
    elif failure == "non_customer":
        s.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(s.reviewer, s.project, "IMPLEMENTATION_MEMBER"),)
    elif failure == "missing_context":
        transition = replace(transition, proof_context=None)
    else:
        s.readiness.prove.side_effect = OutlineReviewReadinessError()
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.require_transition_access_in_transaction(object(), transition)
    s.repo.consume_terminal.assert_not_called()
