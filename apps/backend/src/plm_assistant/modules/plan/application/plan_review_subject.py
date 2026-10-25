"""PLN-02 PlanVersion Subject callbacks for atomic PROJECT Review start."""

from __future__ import annotations

import uuid

from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ProjectReviewerQualificationService,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import (
    AuthorizedReviewCreation, CreatedReviewRef,
)
from plm_assistant.modules.review.application.subject_start import (
    PreparedReviewSubject, ReviewSubjectAccessDenied,
    ReviewSubjectProofContext, ReviewSubjectStartError,
    ReviewSubjectStartRequest,
)

from .plan_review_readiness import (
    PlanReviewReadinessDenied, PlanVersionReviewReadinessQuery,
    PlanVersionReviewReadinessService,
)
_CUSTOMER_CONFIRMERS = frozenset({"CUSTOMER_MANAGER", "CUSTOMER_MEMBER"})


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class PlanReviewSubjectOwner:
    """Start-only internal Subject owner; deliberately not registry-ready."""

    SUBJECT_TYPE = "PLN-02"
    POLICY_CODE = "PLAN_VERSION_ALL_V1"

    def __init__(self, *, repository: object,
                 reviewers: ProjectReviewerQualificationService,
                 readiness: PlanVersionReviewReadinessService) -> None:
        if any(value is None for value in (repository, reviewers, readiness)):
            raise ValueError("Plan Review Subject dependencies required")
        self._repo, self._reviewers, self._readiness = repository, reviewers, readiness

    def authorize_create(self, tx, *, user_id, project_id, subject_type,
                         subject_id, subject_version_id):
        if (not all(_id(value) for value in (
                user_id, project_id, subject_id, subject_version_id))
                or subject_type != self.SUBJECT_TYPE
                or subject_id != subject_version_id):
            return None
        locked = self._repo.lock_subject(
            tx, project_id=project_id, plan_version_id=subject_version_id)
        if (locked is None or locked.snapshot.project_id != project_id
                or locked.snapshot.plan_version_id != subject_version_id
                or locked.latest_version_id != subject_version_id
                or locked.snapshot.version_state != "DRAFT"
                or locked.snapshot.review_ref is not None
                or locked.snapshot.review_round_ref is not None):
            return None
        return AuthorizedReviewCreation(
            user_id, project_id, subject_type, subject_id,
            subject_version_id, self.POLICY_CODE)

    def authorize_replay(self, tx, *, user_id, review: CreatedReviewRef) -> bool:
        return (type(review) is CreatedReviewRef and _id(user_id)
                and review.subject_type == self.SUBJECT_TYPE
                and review.policy_code == self.POLICY_CODE
                and self._repo.version_exists(
                    tx, project_id=review.project_id,
                    plan_version_id=review.subject_id))

    def prepare_start_in_transaction(
            self, tx, request: ReviewSubjectStartRequest) -> PreparedReviewSubject:
        self._request(request)
        self._qualify(tx, request.review.project_id, request.reviewer_ids)
        locked = self._draft_lock(tx, request)
        context = request.proof_context
        if type(context) is not ReviewSubjectProofContext:
            raise ReviewSubjectAccessDenied()
        try:
            proof = self._readiness.prove_in_transaction(
                tx, query=PlanVersionReviewReadinessQuery(
                    context.session_token, context.trace_id,
                    request.review.project_id, locked.snapshot.plan_id,
                    request.subject_version_id))
        except PlanReviewReadinessDenied:
            raise ReviewSubjectAccessDenied() from None
        if (proof.project_id != locked.snapshot.project_id
                or proof.plan_id != locked.snapshot.plan_id
                or proof.plan_version_id != request.subject_version_id
                or proof.version_no != locked.snapshot.version_no):
            raise ReviewSubjectAccessDenied()
        return PreparedReviewSubject(
            request, proof.content_fingerprint, 1, proof.checked_at,
            request.reviewer_ids, ())

    def finalize_start_in_transaction(
            self, tx, request: ReviewSubjectStartRequest) -> None:
        locked = self._draft_lock(tx, request)
        self._repo.bind_start(
            tx, before=locked, review_id=request.review.review_id,
            round_id=request.round_id, actor_id=request.actor_id)

    def assert_active_lock_in_transaction(
            self, tx, request: ReviewSubjectStartRequest) -> None:
        self._request(request)
        locked = self._lock(tx, request)
        version = locked.snapshot
        draft = (version.version_state == "DRAFT"
                 and version.review_ref is None
                 and version.review_round_ref is None)
        active = (version.version_state == "IN_REVIEW"
                  and version.review_ref == request.review.review_id
                  and version.review_round_ref == request.round_id)
        if locked.latest_version_id != request.subject_version_id or not (draft or active):
            raise ReviewSubjectAccessDenied()

    def require_start_replay_access_in_transaction(
            self, tx, *, actor_id, review, round_ref) -> None:
        version_id = getattr(round_ref, "subject_version_id", None)
        if (not _id(actor_id) or not self._valid_review(review)
                or not _id(version_id)
                or version_id != review.subject_id
                or getattr(round_ref, "review_id", None) != review.review_id):
            raise ReviewSubjectAccessDenied()
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id, plan_version_id=version_id)
        if (locked is None or locked.snapshot.review_ref != review.review_id
                or locked.snapshot.review_round_ref != round_ref.round_id):
            raise ReviewSubjectAccessDenied()

    def _draft_lock(self, tx, request):
        self._request(request)
        locked = self._lock(tx, request)
        version = locked.snapshot
        if (version.version_state != "DRAFT" or version.review_ref is not None
                or version.review_round_ref is not None
                or locked.latest_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        return locked

    def _lock(self, tx, request):
        locked = self._repo.lock_subject(
            tx, project_id=request.review.project_id,
            plan_version_id=request.subject_version_id)
        if (locked is None
                or locked.snapshot.project_id != request.review.project_id
                or locked.snapshot.plan_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        return locked

    def _qualify(self, tx, project_id, reviewer_ids):
        try:
            facts = self._reviewers.qualify_in_transaction(
                tx, project_id=project_id, reviewer_ids=reviewer_ids,
                allowed_roles=_CUSTOMER_CONFIRMERS)
        except ReviewReviewerEligibilityError:
            raise ReviewSubjectAccessDenied() from None
        if (type(facts) is not tuple or len(facts) != len(reviewer_ids)
                or any(type(fact) is not ProjectReviewerFacts
                       or fact.user_id != user_id
                       or fact.project_id != project_id
                       or fact.project_role not in _CUSTOMER_CONFIRMERS
                       for fact, user_id in zip(facts, reviewer_ids))):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _request(cls, request):
        if type(request) is not ReviewSubjectStartRequest:
            raise ReviewSubjectStartError()
        request.__post_init__()
        if (not cls._valid_review(request.review)
                or request.review.subject_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _valid_review(cls, review):
        return (getattr(review, "scope", None) == "PROJECT"
                and _id(getattr(review, "project_id", None))
                and _id(getattr(review, "subject_id", None))
                and getattr(review, "subject_type", None) == cls.SUBJECT_TYPE
                and getattr(review, "policy_code", None) == cls.POLICY_CODE)
