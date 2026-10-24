from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import CreatedReviewRef
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
    ReviewSubjectProofContext,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
    ReviewDecisionSnapshot,
    ReviewRoundProgress,
    ReviewWithdrawalSnapshot,
)
from plm_assistant.modules.solution.application.structured_spec_review_readiness import (
    StructuredSpecReviewReadinessError,
    StructuredSpecReviewReadinessProof,
)
from plm_assistant.modules.solution.application.structured_spec_review_subject import (
    StructuredSpecReviewLock,
    StructuredSpecReviewSubjectOwner,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    StructuredSpecValidationSnapshot,
)


NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    actor, reviewer = uuid4(), uuid4()
    project, series, version = uuid4(), uuid4(), uuid4()
    review, round_id, trace_id = uuid4(), uuid4(), uuid4()
    snapshot = StructuredSpecValidationSnapshot(
        project, version, series, "MIGRATION_SPEC", 1, "DRAFT",
        b"c" * 32, b"p" * 32, 1, 1, 1, 0)
    lock = StructuredSpecReviewLock(snapshot, version, None, None, None)
    identity = ReviewIdentitySnapshot(
        review, "PROJECT", project, "SOL-06", series,
        "STRUCTURED_SPEC_ALL_V1", "DRAFT", None, 0)
    context = ReviewSubjectProofContext(b"s" * 32, trace_id)
    request = ReviewSubjectStartRequest(
        actor, identity, round_id, version, (reviewer,), context)
    repository, reviewers, readiness, audit = (Mock() for _ in range(4))
    repository.lock_subject.return_value = lock
    repository.series_exists.return_value = True
    repository.consume_terminal.return_value = uuid4()
    repository.assert_terminal_consumed = Mock(return_value=uuid4())
    reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(reviewer, project, "CUSTOMER_MANAGER"),)
    readiness.prove.return_value = StructuredSpecReviewReadinessProof(
        snapshot, NOW)
    owner = StructuredSpecReviewSubjectOwner(
        repository=repository, reviewers=reviewers,
        readiness=readiness, audit=audit)
    return locals()


def test_create_owner_binds_latest_draft_and_policy(setup):
    s = setup
    proof = s["owner"].authorize_create(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="SOL-06", subject_id=s["series"],
        subject_version_id=s["version"])
    assert proof.policy_code == "STRUCTURED_SPEC_ALL_V1"
    created = CreatedReviewRef(
        s["review"], s["project"], "SOL-06", s["series"],
        "STRUCTURED_SPEC_ALL_V1", s["actor"], NOW)
    assert s["owner"].authorize_replay(
        s["request"], user_id=s["actor"], review=created)
    s["repository"].lock_subject.return_value = replace(
        s["lock"], latest_version_id=uuid4())
    assert s["owner"].authorize_create(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="SOL-06", subject_id=s["series"],
        subject_version_id=s["version"]) is None


def test_read_owner_rechecks_member_series_and_exact_historical_version(setup):
    s = setup
    s["repository"].version_exists.return_value = True
    s["reviewers"].qualify_in_transaction.return_value = (
        ProjectReviewerFacts(s["actor"], s["project"], "CUSTOMER_MEMBER"),)
    current = s["owner"].authorize_read(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="SOL-06", subject_id=s["series"],
        subject_version_id=None)
    assert current.subject_version_id is None
    historical = s["owner"].authorize_read(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="SOL-06", subject_id=s["series"],
        subject_version_id=s["version"])
    assert historical.subject_version_id == s["version"]
    s["repository"].version_exists.assert_called_once_with(
        s["request"], project_id=s["project"], series_id=s["series"],
        spec_id=s["version"])
    assert all(call.kwargs["reviewer_ids"] == (s["actor"],)
               for call in s["reviewers"].qualify_in_transaction.call_args_list)


def test_read_owner_hides_unknown_or_ineligible_subject_facts(setup):
    s = setup
    s["reviewers"].qualify_in_transaction.return_value = (
        ProjectReviewerFacts(s["actor"], s["project"], "PROJECT_MANAGER"),)
    s["repository"].series_exists.return_value = False
    assert s["owner"].authorize_read(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="SOL-06", subject_id=s["series"],
        subject_version_id=None) is None
    s["reviewers"].qualify_in_transaction.side_effect = (
        ReviewReviewerEligibilityError())
    assert s["owner"].authorize_read(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="SOL-06", subject_id=s["series"],
        subject_version_id=s["version"]) is None
    assert s["owner"].authorize_read(
        s["request"], user_id=s["actor"], project_id=s["project"],
        subject_type="REQ-03", subject_id=s["series"],
        subject_version_id=None) is None


def test_prepare_recomputes_current_facts_and_finalizes_binding(setup):
    s = setup
    prepared = s["owner"].prepare_start_in_transaction(
        s["request"], s["request"])
    assert prepared.content_fingerprint == b"c" * 32
    assert prepared.verified_at == NOW
    query = s["readiness"].prove.call_args.kwargs["query"]
    assert query.session_token == b"s" * 32
    assert query.trace_id == s["trace_id"]
    assert query.structured_solution_spec_id == s["version"]
    assert s["readiness"].prove.call_args.kwargs["required_state"] == "DRAFT"
    s["owner"].finalize_start_in_transaction(s["request"], s["request"])
    s["repository"].bind_start.assert_called_once_with(
        s["request"], before=s["lock"], review_id=s["review"],
        round_id=s["round_id"], actor_id=s["actor"])


def test_missing_context_reviewer_or_readiness_failure_closes_gate(setup):
    s = setup
    no_context = replace(s["request"], proof_context=None)
    with pytest.raises(ReviewSubjectAccessDenied):
        s["owner"].prepare_start_in_transaction(no_context, no_context)
    s["reviewers"].qualify_in_transaction.side_effect = (
        ReviewReviewerEligibilityError())
    with pytest.raises(ReviewSubjectAccessDenied):
        s["owner"].prepare_start_in_transaction(s["request"], s["request"])
    s["reviewers"].qualify_in_transaction.side_effect = None
    s["readiness"].prove.side_effect = StructuredSpecReviewReadinessError()
    with pytest.raises(ReviewSubjectAccessDenied):
        s["owner"].prepare_start_in_transaction(s["request"], s["request"])


def test_terminal_approval_revalidates_consumes_and_audits_series(setup):
    s = setup
    transition, active = _terminal(s, "APPROVE")
    s["owner"].require_transition_access_in_transaction(transition, transition)
    assert s["readiness"].prove.call_args.kwargs["required_state"] == "IN_REVIEW"
    s["owner"].consume_terminal_in_transaction(transition, transition)
    s["repository"].consume_terminal.assert_called_once_with(
        transition, before=active, transition=transition,
        version_state="APPROVED")
    s["owner"].assert_terminal_consumed_in_transaction(
        transition, transition)
    event = s["audit"].append.call_args.args[1]
    assert event.action == "STRUCTURED_SPEC_VERSION_APPROVED"
    assert event.target_object_id == s["series"]
    assert event.target_version_id == s["version"]
    assert event.after_state == "APPROVED"


def test_withdrawal_does_not_require_current_fact_recheck(setup):
    s = setup
    active = replace(
        s["lock"], snapshot=replace(s["snapshot"], version_state="IN_REVIEW"),
        review_ref=s["review"], review_round_ref=s["round_id"])
    s["repository"].lock_subject.return_value = active
    other = uuid4()
    progress = ReviewRoundProgress(s["round_id"], NOW, (s["reviewer"], other))
    fixed = _fixed(s, progress)
    transition = ReviewSubjectTransition(
        s["actor"], s["trace_id"], fixed,
        progress.withdraw(ReviewWithdrawalSnapshot(
            s["actor"], NOW, "Source changed")), NOW,
        s["context"])
    s["readiness"].prove.reset_mock()
    s["owner"].require_transition_access_in_transaction(transition, transition)
    s["owner"].consume_terminal_in_transaction(transition, transition)
    s["repository"].consume_terminal.assert_called_once_with(
        transition, before=active, transition=transition,
        version_state="RETURNED")
    s["readiness"].prove.assert_not_called()


def _terminal(s, decision_name):
    active = replace(
        s["lock"], snapshot=replace(s["snapshot"], version_state="IN_REVIEW"),
        review_ref=s["review"], review_round_ref=s["round_id"])
    s["repository"].lock_subject.return_value = active
    s["readiness"].prove.return_value = StructuredSpecReviewReadinessProof(
        active.snapshot, NOW)
    progress = ReviewRoundProgress(s["round_id"], NOW, (s["reviewer"],))
    fixed = _fixed(s, progress)
    decision = ReviewDecisionSnapshot(
        uuid4(), s["round_id"], s["reviewer"],
        ReviewDecisionKind[decision_name], NOW)
    return ReviewSubjectTransition(
        s["reviewer"], s["trace_id"], fixed,
        progress.record_decision(decision), NOW, s["context"]), active


def _fixed(s, progress):
    review = replace(
        s["identity"], state="IN_REVIEW", active_round_id=s["round_id"],
        lock_version=1)
    return FixedReviewRoundSnapshot(
        review, 1, s["version"], s["actor"], progress,
        tuple(uuid4() for _ in progress.reviewer_ids), 0, uuid4(),
        b"c" * 32, 1, NOW, (), uuid4(), NOW, None)
