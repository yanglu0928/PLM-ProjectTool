"""PlanVersion SubmitReview is one authorized Create/Start command."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanVersionReviewLock, PlanVersionReviewReadinessProof,
)
from plm_assistant.modules.plan.application.plan_review_subject import (
    PlanReviewSubjectOwner,
)
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionSnapshotView,
)
from plm_assistant.modules.plan.application.submit_plan_version_review import (
    PlanVersionReviewSubmissionError, PlanVersionReviewSubmissionService,
    SubmitPlanVersionReview,
)
from plm_assistant.modules.review.application.create_review import (
    CreatedReviewRef,
)
from plm_assistant.modules.review.application.project_persistence import (
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)


NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


class Transaction:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        type(self).commits += 1


@pytest.fixture
def subject_setup():
    project, plan, version, actor, reviewer, trace, review_id, round_id = (
        uuid4() for _ in range(8))
    snapshot = PlanVersionSnapshotView(
        version, plan, project, 1, "DRAFT", actor, NOW, None, None, None,
        {"calendar_ref": None, "wbs_items": [], "dependencies": [],
         "milestones": [], "exclusions": []},
    )
    lock = PlanVersionReviewLock(snapshot, version)
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, "PLN-02", version,
        "PLAN_VERSION_ALL_V1", "DRAFT", None, 0)
    request = ReviewSubjectStartRequest(
        actor, identity, round_id, version, (reviewer,),
        ReviewSubjectProofContext(b"s" * 32, trace))
    repo, reviewers, readiness = Mock(), Mock(), Mock()
    repo.lock_subject.return_value = lock
    repo.version_exists.return_value = True
    reviewers.qualify_in_transaction.return_value = (
        ProjectReviewerFacts(reviewer, project, "CUSTOMER_MANAGER"),)
    readiness.prove_in_transaction.return_value = PlanVersionReviewReadinessProof(
        project, plan, version, 1, b"f" * 32, NOW)
    owner = PlanReviewSubjectOwner(
        repository=repo, reviewers=reviewers, readiness=readiness)
    return SimpleNamespace(**locals())


def test_subject_authorizes_fixed_latest_draft_and_start_proof(subject_setup):
    s = subject_setup
    created = CreatedReviewRef(
        s.review_id, s.project, "PLN-02", s.version,
        "PLAN_VERSION_ALL_V1", s.actor, NOW)
    authorized = s.owner.authorize_create(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="PLN-02", subject_id=s.version,
        subject_version_id=s.version)
    assert authorized.policy_code == "PLAN_VERSION_ALL_V1"
    assert s.owner.authorize_replay(object(), user_id=s.actor, review=created)
    prepared = s.owner.prepare_start_in_transaction(object(), s.request)
    assert prepared.content_fingerprint == b"f" * 32
    assert prepared.qualified_reviewer_ids == (s.reviewer,)
    query = s.readiness.prove_in_transaction.call_args.kwargs["query"]
    assert (query.project_id, query.plan_id, query.plan_version_id) == (
        s.project, s.plan, s.version)
    s.repo.lock_subject.return_value = PlanVersionReviewLock(
        s.snapshot, uuid4())
    assert s.owner.authorize_create(
        object(), user_id=s.actor, project_id=s.project,
        subject_type="PLN-02", subject_id=s.version,
        subject_version_id=s.version) is None


def test_subject_rejects_stale_or_unbound_review_and_binds_start(subject_setup):
    s = subject_setup
    s.owner.finalize_start_in_transaction(object(), s.request)
    s.repo.bind_start.assert_called_once_with(
        s.repo.bind_start.call_args.args[0], before=s.lock,
        review_id=s.review_id, round_id=s.round_id, actor_id=s.actor)
    assert s.owner.assert_active_lock_in_transaction(object(), s.request) is None
    wrong_identity = ReviewIdentitySnapshot(
        s.review_id, "PROJECT", s.project, "PLN-02", uuid4(),
        "PLAN_VERSION_ALL_V1", "DRAFT", None, 0)
    wrong_request = ReviewSubjectStartRequest(
        s.actor, wrong_identity, s.round_id, s.version, (s.reviewer,),
        ReviewSubjectProofContext(b"s" * 32, s.trace))
    with pytest.raises(ReviewSubjectAccessDenied):
        s.owner.prepare_start_in_transaction(object(), wrong_request)
    assert s.readiness.prove_in_transaction.call_count == 0


def test_submit_owner_composes_authorization_receipt_and_review_once():
    actor, project, plan, version, reviewer, trace = (uuid4() for _ in range(6))
    round_id, review_id = uuid4(), uuid4()
    command = SubmitPlanVersionReview(
        b"s" * 32, b"c" * 32, trace, project, plan, version,
        (reviewer,), "PLAN_VERSION_ALL_V1", str(uuid4()))
    access, guard, authorization, reviewers, receipts, replays, reviews, subjects, scope = (
        Mock() for _ in range(9))
    access.authenticated_user.return_value = actor
    authorization.require_in_transaction.return_value = AuthorizedProjectAction(
        actor, project, "PLAN_VERSION_SUBMIT_REVIEW", "PROJECT_MANAGER")
    receipts.reserve.return_value = None
    scope.version_belongs_to_plan.return_value = True
    reviews.submit_in_transaction.return_value = SubmittedProjectReviewRef(
        review_id, round_id, project, "PLN-02", version, version,
        "PLAN_VERSION_ALL_V1", (reviewer,), actor, NOW)
    reviews.is_retryable_deadlock.return_value = False
    replays.is_retryable_deadlock.return_value = False
    Transaction.commits = 0
    service = PlanVersionReviewSubmissionService(
        unit_of_work=Transaction, access=access, license_guard=guard,
        authorization=authorization, reviewers=reviewers, receipts=receipts,
        replay_repository=replays, reviews=reviews, subjects=subjects,
        scope_repository=scope,
        clock=lambda: NOW)
    result = service.submit(command)
    assert result.round_id == round_id
    assert Transaction.commits == 1
    receipts.complete.assert_called_once()
    reviews.submit_in_transaction.assert_called_once()
    assert reviews.submit_in_transaction.call_args.kwargs["proof_context"].session_token == b"s" * 32


def test_submit_owner_does_not_commit_when_project_permission_denied():
    actor, project, plan, version, reviewer, trace = (uuid4() for _ in range(6))
    command = SubmitPlanVersionReview(
        b"s" * 32, b"c" * 32, trace, project, plan, version,
        (reviewer,), "PLAN_VERSION_ALL_V1", str(uuid4()))
    access, guard, authorization, reviewers, receipts, replays, reviews, subjects, scope = (
        Mock() for _ in range(9))
    access.authenticated_user.return_value = actor
    authorization.require_in_transaction.return_value = SimpleNamespace()
    Transaction.commits = 0
    service = PlanVersionReviewSubmissionService(
        unit_of_work=Transaction, access=access, license_guard=guard,
        authorization=authorization, reviewers=reviewers, receipts=receipts,
        replay_repository=replays, reviews=reviews, subjects=subjects,
        scope_repository=scope,
        clock=lambda: NOW)
    with pytest.raises(PlanVersionReviewSubmissionError) as error:
        service.submit(command)
    assert error.value.code == "RESOURCE_NOT_FOUND"
    assert Transaction.commits == 0
    reviews.submit_in_transaction.assert_not_called()


def test_submit_owner_rejects_version_from_another_plan_before_receipt():
    actor, project, plan, version, reviewer, trace = (uuid4() for _ in range(6))
    command = SubmitPlanVersionReview(
        b"s" * 32, b"c" * 32, trace, project, plan, version,
        (reviewer,), "PLAN_VERSION_ALL_V1", str(uuid4()))
    access, guard, authorization, reviewers, receipts, replays, reviews, subjects, scope = (
        Mock() for _ in range(9))
    access.authenticated_user.return_value = actor
    authorization.require_in_transaction.return_value = AuthorizedProjectAction(
        actor, project, "PLAN_VERSION_SUBMIT_REVIEW", "PROJECT_MANAGER")
    scope.version_belongs_to_plan.return_value = False
    Transaction.commits = 0
    service = PlanVersionReviewSubmissionService(
        unit_of_work=Transaction, access=access, license_guard=guard,
        authorization=authorization, reviewers=reviewers, receipts=receipts,
        replay_repository=replays, reviews=reviews, subjects=subjects,
        scope_repository=scope, clock=lambda: NOW)
    with pytest.raises(PlanVersionReviewSubmissionError) as error:
        service.submit(command)
    assert error.value.code == "RESOURCE_NOT_FOUND"
    receipts.reserve.assert_not_called()
    reviews.submit_in_transaction.assert_not_called()
    assert Transaction.commits == 0
