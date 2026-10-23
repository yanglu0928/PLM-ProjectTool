"""SOL-05 SectionVersion PROJECT Review start Owner; terminal remains closed."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.project.application.authorization import ALL_MEMBERS
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ProjectReviewerQualificationService,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import (
    AuthorizedReviewCreation, CreatedReviewRef,
)
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewSubjectRead,
)
from plm_assistant.modules.review.application.subject_start import (
    PreparedReviewSubject, ReviewSubjectAccessDenied,
    ReviewSubjectProofContext, ReviewSubjectStartError, ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransitionError,
)

from .read_section_version import SectionVersionHistoryView
from .section_review_readiness import (
    SectionReviewReadinessError, SectionReviewReadinessProof,
    SectionReviewReadinessService,
)
from .section_version_validation_contract import SectionCurrentFactQuery

_CUSTOMER_CONFIRMERS = frozenset({"CUSTOMER_MANAGER", "CUSTOMER_MEMBER"})


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


@dataclass(frozen=True, slots=True)
class SectionReviewLock:
    version: SectionVersionHistoryView
    latest_version_id: uuid.UUID
    current_approved_version_ref: uuid.UUID | None

    def __post_init__(self) -> None:
        if (type(self.version) is not SectionVersionHistoryView
                or not _id(self.latest_version_id)
                or self.current_approved_version_ref is not None
                and not _id(self.current_approved_version_ref)):
            raise ReviewSubjectStartError()


class SectionReviewRepositoryPort(Protocol):
    def lock_subject(self, transaction: object, *, project_id: uuid.UUID,
                     section_id: uuid.UUID,
                     version_id: uuid.UUID) -> SectionReviewLock | None: ...
    def section_exists(self, transaction: object, *, project_id: uuid.UUID,
                       section_id: uuid.UUID) -> bool: ...
    def version_exists(self, transaction: object, *, project_id: uuid.UUID,
                       section_id: uuid.UUID, version_id: uuid.UUID) -> bool: ...
    def bind_start(self, transaction: object, *, before: SectionReviewLock,
                   review_id: uuid.UUID, round_id: uuid.UUID,
                   actor_id: uuid.UUID) -> None: ...


class SectionReviewSubjectOwner:
    """Owns exact Section Review start; no terminal decision is implied."""

    SUBJECT_TYPE = "SOL-05"
    POLICY_CODE = "SOLUTION_SECTION_ALL_V1"

    def __init__(self, *, repository: SectionReviewRepositoryPort,
                 reviewers: ProjectReviewerQualificationService,
                 readiness: SectionReviewReadinessService) -> None:
        if any(value is None for value in (repository, reviewers, readiness)):
            raise ValueError("Section Review dependencies required")
        self._repo, self._reviewers, self._readiness = (
            repository, reviewers, readiness)

    def authorize_create(self, tx: object, *, user_id: uuid.UUID,
                         project_id: uuid.UUID, subject_type: str,
                         subject_id: uuid.UUID,
                         subject_version_id: uuid.UUID,
                         ) -> AuthorizedReviewCreation | None:
        if (not all(_id(item) for item in (
                user_id, project_id, subject_id, subject_version_id))
                or subject_type != self.SUBJECT_TYPE):
            return None
        locked = self._repo.lock_subject(
            tx, project_id=project_id, section_id=subject_id,
            version_id=subject_version_id)
        if (type(locked) is not SectionReviewLock
                or locked.version.project_id != project_id
                or locked.version.solution_section_id != subject_id
                or locked.version.solution_section_version_id != subject_version_id
                or locked.version.version_state != "DRAFT"
                or locked.version.review_ref is not None
                or locked.version.review_round_ref is not None
                or locked.latest_version_id != subject_version_id):
            return None
        return AuthorizedReviewCreation(
            user_id, project_id, subject_type, subject_id,
            subject_version_id, self.POLICY_CODE)

    def authorize_replay(self, tx: object, *, user_id: uuid.UUID,
                         review: CreatedReviewRef) -> bool:
        return (type(review) is CreatedReviewRef and _id(user_id)
                and _id(review.project_id) and _id(review.subject_id)
                and review.subject_type == self.SUBJECT_TYPE
                and review.policy_code == self.POLICY_CODE
                and self._repo.section_exists(
                    tx, project_id=review.project_id,
                    section_id=review.subject_id) is True)

    def authorize_read(self, tx: object, *, user_id: uuid.UUID,
                       project_id: uuid.UUID, subject_type: str,
                       subject_id: uuid.UUID,
                       subject_version_id: uuid.UUID | None,
                       ) -> AuthorizedReviewSubjectRead | None:
        if (not all(_id(item) for item in (user_id, project_id, subject_id))
                or subject_type != self.SUBJECT_TYPE
                or subject_version_id is not None and not _id(subject_version_id)):
            return None
        try:
            self._qualify(tx, project_id=project_id, reviewer_ids=(user_id,),
                          allowed_roles=ALL_MEMBERS)
        except ReviewSubjectAccessDenied:
            return None
        exists = (self._repo.section_exists(
            tx, project_id=project_id, section_id=subject_id)
            if subject_version_id is None else self._repo.version_exists(
                tx, project_id=project_id, section_id=subject_id,
                version_id=subject_version_id))
        if exists is not True:
            return None
        return AuthorizedReviewSubjectRead(
            user_id, project_id, subject_type, subject_id, subject_version_id)

    def prepare_start_in_transaction(
            self, tx: object, request: ReviewSubjectStartRequest,
            ) -> PreparedReviewSubject:
        self._request(request)
        self._qualify(tx, project_id=request.review.project_id,
                      reviewer_ids=request.reviewer_ids)
        locked = self._draft_lock(tx, request)
        context = request.proof_context
        if type(context) is not ReviewSubjectProofContext:
            raise ReviewSubjectAccessDenied()
        try:
            proof = self._readiness.prove(tx, query=SectionCurrentFactQuery(
                context.session_token, context.trace_id,
                request.review.project_id, request.review.subject_id,
                request.subject_version_id))
        except SectionReviewReadinessError:
            raise ReviewSubjectAccessDenied() from None
        if (type(proof) is not SectionReviewReadinessProof
                or proof.version != locked.version
                or proof.content_fingerprint
                != locked.version.content_fingerprint):
            raise ReviewSubjectAccessDenied()
        return PreparedReviewSubject(
            request, proof.content_fingerprint, 1, proof.verified_at,
            request.reviewer_ids, ())

    def finalize_start_in_transaction(
            self, tx: object, request: ReviewSubjectStartRequest) -> None:
        locked = self._draft_lock(tx, request)
        self._repo.bind_start(
            tx, before=locked, review_id=request.review.review_id,
            round_id=request.round_id, actor_id=request.actor_id)

    def assert_active_lock_in_transaction(
            self, tx: object, request: ReviewSubjectStartRequest) -> None:
        self._request(request)
        locked = self._lock(tx, request)
        version = locked.version
        draft = (version.version_state == "DRAFT"
                 and version.review_ref is None
                 and version.review_round_ref is None)
        active = (version.version_state == "IN_REVIEW"
                  and version.review_ref == request.review.review_id
                  and version.review_round_ref == request.round_id)
        if locked.latest_version_id != request.subject_version_id or not (
                draft or active):
            raise ReviewSubjectAccessDenied()

    def require_start_replay_access_in_transaction(
            self, tx: object, *, actor_id: uuid.UUID, review,
            round_ref) -> None:
        version_id = getattr(round_ref, "subject_version_id", None)
        if (not _id(actor_id) or not self._valid_review(review)
                or not _id(version_id)
                or getattr(round_ref, "review_id", None) != review.review_id):
            raise ReviewSubjectAccessDenied()
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id, section_id=review.subject_id,
            version_id=version_id)
        if (type(locked) is not SectionReviewLock
                or locked.version.review_ref != review.review_id
                or locked.version.review_round_ref
                != getattr(round_ref, "round_id", None)):
            raise ReviewSubjectAccessDenied()

    # Registry requires the complete protocol. Terminal callbacks fail closed
    # until the separately tested customer-decision Owner is installed.
    def require_transition_access_in_transaction(self, tx, transition):
        raise ReviewSubjectTransitionError()

    def assert_transition_lock_in_transaction(self, tx, transition):
        raise ReviewSubjectTransitionError()

    def consume_terminal_in_transaction(self, tx, transition):
        raise ReviewSubjectTransitionError()

    def assert_terminal_consumed_in_transaction(self, tx, transition):
        raise ReviewSubjectTransitionError()

    def require_transition_replay_access_in_transaction(
            self, tx, *, actor_id, review, result):
        raise ReviewSubjectTransitionError()

    def _draft_lock(self, tx, request) -> SectionReviewLock:
        self._request(request)
        locked = self._lock(tx, request)
        if (locked.version.version_state != "DRAFT"
                or locked.version.review_ref is not None
                or locked.version.review_round_ref is not None
                or locked.latest_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        return locked

    def _lock(self, tx, request) -> SectionReviewLock:
        locked = self._repo.lock_subject(
            tx, project_id=request.review.project_id,
            section_id=request.review.subject_id,
            version_id=request.subject_version_id)
        if (type(locked) is not SectionReviewLock
                or locked.version.project_id != request.review.project_id
                or locked.version.solution_section_id != request.review.subject_id
                or locked.version.solution_section_version_id
                != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        locked.__post_init__()
        return locked

    def _qualify(self, tx, *, project_id: uuid.UUID,
                 reviewer_ids: tuple[uuid.UUID, ...],
                 allowed_roles: frozenset[str] = _CUSTOMER_CONFIRMERS) -> None:
        try:
            facts = self._reviewers.qualify_in_transaction(
                tx, project_id=project_id, reviewer_ids=reviewer_ids,
                allowed_roles=allowed_roles)
        except ReviewReviewerEligibilityError:
            raise ReviewSubjectAccessDenied() from None
        if (type(facts) is not tuple or len(facts) != len(reviewer_ids)
                or any(type(fact) is not ProjectReviewerFacts
                       or fact.user_id != user_id
                       or fact.project_id != project_id
                       or fact.project_role not in allowed_roles
                       for fact, user_id in zip(facts, reviewer_ids))):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _request(cls, request: object) -> None:
        if type(request) is not ReviewSubjectStartRequest:
            raise ReviewSubjectStartError()
        request.__post_init__()
        if not cls._valid_review(request.review):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _valid_review(cls, review: object) -> bool:
        return (getattr(review, "scope", None) == "PROJECT"
                and _id(getattr(review, "project_id", None))
                and _id(getattr(review, "subject_id", None))
                and getattr(review, "subject_type", None) == cls.SUBJECT_TYPE
                and getattr(review, "policy_code", None) == cls.POLICY_CODE)
