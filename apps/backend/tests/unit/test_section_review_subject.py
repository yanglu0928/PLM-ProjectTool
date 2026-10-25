"""SOL-05 Review starts only from the exact current, eligible DRAFT."""

from __future__ import annotations

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
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot
from plm_assistant.modules.review.application.read_snapshot import FixedReviewRoundSnapshot
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition, ReviewSubjectTransitionError,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
    ReviewWithdrawalSnapshot,
)
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_review_readiness import (
    SectionReviewReadinessError, SectionReviewReadinessProof,
)
from plm_assistant.modules.solution.application.section_review_subject import (
    SectionReviewLock, SectionReviewSubjectOwner,
)
from plm_assistant.modules.solution.application.section_version_validation_contract import (
    SectionVersionValidationFacts,
)


NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    project, section, version, actor, reviewer, trace = (uuid4() for _ in range(6))
    review_id, round_id = uuid4(), uuid4()
    fixed = SectionVersionHistoryView(
        version, section, project, 1, "DRAFT", "Section", uuid4(), None,
        b"x" * 32, (), (), (), (), None, None, None, actor, NOW,
        "NONE_REQUIRED", "No structured spec", ())
    lock = SectionReviewLock(fixed, version, None)
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, "SOL-05", section,
        "SOLUTION_SECTION_ALL_V1", "DRAFT", None, 0)
    request = ReviewSubjectStartRequest(
        actor, identity, round_id, version, (reviewer,),
        ReviewSubjectProofContext(b"s" * 32, trace))
    repo, reviewers, readiness = Mock(), Mock(), Mock()
    repo.lock_subject.return_value = lock
    repo.section_exists.return_value = True
    repo.version_exists.return_value = True
    repo.consume_terminal.return_value = uuid4()
    repo.assert_terminal_consumed = Mock(return_value=uuid4())
    reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(reviewer, project, "CUSTOMER_MANAGER"),)
    readiness.prove.return_value = SectionReviewReadinessProof(
        fixed, SectionVersionValidationFacts(*(["PASS"] * 6)),
        NOW, fixed.content_fingerprint)
    audit = Mock()
    owner = SectionReviewSubjectOwner(
        repository=repo, reviewers=reviewers, readiness=readiness,
        audit=audit)
    return SimpleNamespace(**locals())


def test_create_is_exact_latest_draft_and_replay_is_history_safe(setup):
    s = setup
    result = s.owner.authorize_create(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="SOL-05", subject_id=s.section,
        subject_version_id=s.version)
    assert result.policy_code == "SOLUTION_SECTION_ALL_V1"
    created = CreatedReviewRef(
        s.review_id, s.project, "SOL-05", s.section,
        "SOLUTION_SECTION_ALL_V1", s.actor, NOW)
    assert s.owner.authorize_replay(object(), user_id=s.actor, review=created)
    s.repo.lock_subject.return_value = replace(
        s.lock, latest_version_id=uuid4())
    assert s.owner.authorize_create(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="SOL-05", subject_id=s.section,
        subject_version_id=s.version) is None


def test_prepare_rechecks_current_six_dimensions_and_exact_snapshot(setup):
    s = setup
    prepared = s.owner.prepare_start_in_transaction(object(), s.request)
    assert prepared.content_fingerprint == s.fixed.content_fingerprint
    assert prepared.qualified_reviewer_ids == (s.reviewer,)
    query = s.readiness.prove.call_args.kwargs["query"]
    assert (query.project_id, query.solution_section_id,
            query.solution_section_version_id) == (
                s.project, s.section, s.version)
    s.owner.finalize_start_in_transaction(object(), s.request)
    assert s.repo.bind_start.call_args.kwargs["before"] == s.lock
    s.owner.assert_active_lock_in_transaction(object(), s.request)
    s.repo.lock_subject.return_value = replace(s.lock, version=replace(
        s.fixed, version_state="IN_REVIEW", review_ref=s.review_id,
        review_round_ref=s.round_id))
    s.owner.assert_active_lock_in_transaction(object(), s.request)


def test_missing_context_ineligible_reviewer_or_stale_fact_fails_closed(setup):
    s = setup
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(
            object(), replace(s.request, proof_context=None))
    s.reviewers.qualify_in_transaction.side_effect = (
        ReviewReviewerEligibilityError())
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(object(), s.request)
    s.reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(s.reviewer, s.project, "IMPLEMENTATION_MEMBER"),)
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(object(), s.request)
    s.reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(s.reviewer, s.project, "CUSTOMER_MANAGER"),)
    s.reviewers.qualify_in_transaction.side_effect = None
    s.readiness.prove.side_effect = SectionReviewReadinessError()
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(object(), s.request)
    s.readiness.prove.side_effect = None
    s.readiness.prove.return_value = replace(
        s.readiness.prove.return_value,
        version=replace(s.fixed, content_fingerprint=b"z" * 32),
        content_fingerprint=b"z" * 32)
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(object(), s.request)


def test_read_rechecks_membership_and_exact_version(setup):
    s = setup
    s.reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(s.actor, s.project, "CUSTOMER_MEMBER"),)
    assert s.owner.authorize_read(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="SOL-05", subject_id=s.section,
        subject_version_id=s.version).subject_version_id == s.version
    s.repo.version_exists.return_value = False
    assert s.owner.authorize_read(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="SOL-05", subject_id=s.section,
        subject_version_id=s.version) is None


def test_terminal_callbacks_remain_closed(setup):
    for name in (
            "require_transition_access_in_transaction",
            "assert_transition_lock_in_transaction",
            "consume_terminal_in_transaction",
            "assert_terminal_consumed_in_transaction"):
        with pytest.raises(ReviewSubjectTransitionError):
            getattr(setup.owner, name)(object(), object())


def _transition(s, kind="APPROVE"):
    active = replace(s.lock, version=replace(
        s.fixed, version_state="IN_REVIEW", review_ref=s.review_id,
        review_round_ref=s.round_id))
    s.repo.lock_subject.return_value = active
    s.readiness.prove.return_value = SectionReviewReadinessProof(
        active.version, SectionVersionValidationFacts(*(["PASS"] * 6)),
        NOW, active.version.content_fingerprint, "IN_REVIEW")
    progress = ReviewRoundProgress(s.round_id, NOW, (s.reviewer,))
    identity = replace(s.identity, state="IN_REVIEW",
                       active_round_id=s.round_id, lock_version=1)
    before = FixedReviewRoundSnapshot(
        identity, 1, s.version, s.actor, progress, (uuid4(),), 0,
        uuid4(), s.fixed.content_fingerprint, 1, NOW, (), uuid4(), NOW, None)
    decision = ReviewDecisionSnapshot(
        uuid4(), s.round_id, s.reviewer,
        ReviewDecisionKind[kind], NOW,
        "Needs changes" if kind == "RETURN" else None)
    return ReviewSubjectTransition(
        s.reviewer, s.trace, before, progress.record_decision(decision),
        NOW, s.request.proof_context), active


def test_terminal_approval_reproves_current_six_dimensions_and_audits(setup):
    s = setup
    transition, active = _transition(s)
    s.owner.require_transition_access_in_transaction(object(), transition)
    assert s.readiness.prove.call_args.kwargs["required_state"] == "IN_REVIEW"
    s.owner.assert_transition_lock_in_transaction(object(), transition)
    s.owner.consume_terminal_in_transaction(object(), transition)
    assert s.repo.consume_terminal.call_args.kwargs == dict(
        before=active, transition=transition, version_state="APPROVED")
    event = s.audit.append.call_args.args[1]
    assert event.action == "SOLUTION_SECTION_VERSION_APPROVED"
    assert event.target_object_id == s.section
    assert event.target_version_id == s.version
    s.owner.assert_terminal_consumed_in_transaction(object(), transition)


@pytest.mark.parametrize("failure", [
    "stale_fingerprint", "wrong_round", "non_customer", "missing_context",
    "source_unavailable",
])
def test_terminal_approval_fails_closed_on_stale_binding_or_fact(setup, failure):
    s = setup
    transition, active = _transition(s)
    if failure == "stale_fingerprint":
        s.repo.lock_subject.return_value = replace(
            active, version=replace(active.version,
                                    content_fingerprint=b"z" * 32))
    elif failure == "wrong_round":
        s.repo.lock_subject.return_value = replace(
            active, version=replace(active.version, review_round_ref=uuid4()))
    elif failure == "non_customer":
        s.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(s.reviewer, s.project,
                                 "IMPLEMENTATION_MEMBER"),)
    elif failure == "missing_context":
        transition = replace(transition, proof_context=None)
    else:
        s.readiness.prove.side_effect = SectionReviewReadinessError()
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.require_transition_access_in_transaction(object(), transition)
    s.repo.consume_terminal.assert_not_called()


def test_return_and_withdraw_do_not_requalify_for_approval(setup):
    s = setup
    transition, active = _transition(s, "RETURN")
    s.owner.require_transition_access_in_transaction(object(), transition)
    s.readiness.prove.assert_not_called()
    s.owner.consume_terminal_in_transaction(object(), transition)
    assert s.repo.consume_terminal.call_args.kwargs["version_state"] == "RETURNED"
    s.repo.consume_terminal.reset_mock()
    s.audit.append.reset_mock()
    s.reviewers.qualify_in_transaction.reset_mock()
    s.readiness.prove.reset_mock()
    progress = transition.before.progress
    withdrawal = ReviewWithdrawalSnapshot(s.actor, NOW, "Source changed")
    transition = ReviewSubjectTransition(
        s.actor, s.trace, transition.before,
        progress.withdraw(withdrawal), NOW, s.request.proof_context)
    s.owner.require_transition_access_in_transaction(object(), transition)
    s.owner.consume_terminal_in_transaction(object(), transition)
    assert s.repo.consume_terminal.call_args.kwargs["version_state"] == "RETURNED"
    s.readiness.prove.assert_not_called()
