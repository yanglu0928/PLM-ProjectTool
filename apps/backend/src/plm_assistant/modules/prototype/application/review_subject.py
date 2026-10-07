"""Prototype-owned PROJECT Review Subject facts and terminal consumption."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts,
    ProjectReviewerQualificationService,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import (
    AuthorizedReviewCreation,
    CreatedReviewRef,
)
from plm_assistant.modules.review.application.subject_start import (
    PreparedReviewSubject,
    ReviewSubjectAccessDenied,
    ReviewSubjectStartError,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
    ReviewSubjectTransitionError,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState

from .create_version import PrototypeVersionInitialView
from .current_version import PrototypeVersionCurrentValidator


@dataclass(frozen=True, slots=True)
class PrototypeReviewLock:
    snapshot: PrototypeVersionInitialView
    prototype_state: str
    prototype_lock_version: int
    current_approved_version_ref: uuid.UUID | None
    latest_version_id: uuid.UUID
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not PrototypeVersionInitialView
                or self.prototype_state not in {
                    "ACTIVE", "NOT_REQUIRED", "ARCHIVED", "RESTRICTED",
                }
                or type(self.prototype_lock_version) is not int
                or self.prototype_lock_version < 0
                or not _uuid(self.latest_version_id)
                or (self.current_approved_version_ref is not None
                    and not _uuid(self.current_approved_version_ref))
                or (self.review_ref is None) !=
                   (self.review_round_ref is None)
                or (self.review_ref is not None
                    and (not _uuid(self.review_ref)
                         or not _uuid(self.review_round_ref)))):
            raise ReviewSubjectStartError()


class PrototypeReviewRepositoryPort(Protocol):
    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
    ) -> PrototypeReviewLock | None: ...

    def active_prototype_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID,
    ) -> bool: ...

    def bind_start(
        self, transaction: object, *, before: PrototypeReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None: ...

    def consume_terminal(
        self, transaction: object, *, before: PrototypeReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None: ...

    def assert_terminal_consumed(
        self, transaction: object, *, transition: ReviewSubjectTransition,
        version_state: str,
    ) -> None: ...


class PrototypeReviewSubjectOwner:
    """Real PRT-03 owner for Review identity, start and formalization."""

    SUBJECT_TYPE = "PRT-03"
    POLICY_CODE = "PROTOTYPE_ALL_V1"

    def __init__(self, *, repository: PrototypeReviewRepositoryPort,
                 reviewers: ProjectReviewerQualificationService,
                 current: PrototypeVersionCurrentValidator, audit: object,
                 clock=None) -> None:
        if any(value is None for value in (
                repository, reviewers, current, audit)):
            raise ValueError("Prototype Review Subject dependencies required")
        self._repo, self._reviewers = repository, reviewers
        self._current, self._audit = current, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def authorize_create(
        self, tx: object, *, user_id: uuid.UUID, project_id: uuid.UUID,
        subject_type: str, subject_id: uuid.UUID,
        subject_version_id: uuid.UUID,
    ) -> AuthorizedReviewCreation | None:
        if (not _ids(user_id, project_id, subject_id, subject_version_id)
                or subject_type != self.SUBJECT_TYPE):
            return None
        locked = self._repo.lock_subject(
            tx, project_id=project_id, prototype_id=subject_id,
            prototype_version_id=subject_version_id,
        )
        if (type(locked) is not PrototypeReviewLock
                or locked.prototype_state != "ACTIVE"
                or locked.snapshot.project_id != project_id
                or locked.snapshot.prototype_id != subject_id
                or locked.snapshot.prototype_version_id != subject_version_id
                or locked.snapshot.version_state != "DRAFT"
                or locked.latest_version_id != subject_version_id
                or locked.review_ref is not None):
            return None
        return AuthorizedReviewCreation(
            user_id, project_id, subject_type, subject_id,
            subject_version_id, self.POLICY_CODE,
        )

    def authorize_replay(
        self, tx: object, *, user_id: uuid.UUID, review: CreatedReviewRef,
    ) -> bool:
        if (type(review) is not CreatedReviewRef
                or not _ids(user_id, review.project_id, review.subject_id)
                or review.subject_type != self.SUBJECT_TYPE
                or review.policy_code != self.POLICY_CODE):
            return False
        return self._repo.active_prototype_exists(
            tx, project_id=review.project_id,
            prototype_id=review.subject_id,
        ) is True

    def prepare_start_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> PreparedReviewSubject:
        self._require_request(request)
        self._qualify_reviewer_ids(
            tx, project_id=request.review.project_id,
            reviewer_ids=request.reviewer_ids,
        )
        locked = self._require_lock(tx, request)
        if (locked.prototype_state != "ACTIVE"
                or locked.snapshot.version_state != "DRAFT"
                or locked.review_ref is not None
                or locked.latest_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        self._validate_current(tx, locked)
        return PreparedReviewSubject(
            request, bytes.fromhex(locked.snapshot.content_fingerprint), 1,
            self._now(), request.reviewer_ids, (),
        )

    def finalize_start_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> None:
        self._require_request(request)
        locked = self._require_lock(tx, request)
        if (locked.prototype_state != "ACTIVE"
                or locked.snapshot.version_state != "DRAFT"
                or locked.review_ref is not None
                or locked.latest_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        self._repo.bind_start(
            tx, before=locked, review_id=request.review.review_id,
            round_id=request.round_id, actor_id=request.actor_id,
        )

    def assert_active_lock_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> None:
        self._require_request(request)
        locked = self._require_lock(tx, request)
        draft = (locked.snapshot.version_state == "DRAFT"
                 and locked.review_ref is None
                 and locked.review_round_ref is None)
        active = (locked.snapshot.version_state == "IN_REVIEW"
                  and locked.review_ref == request.review.review_id
                  and locked.review_round_ref == request.round_id)
        if (locked.prototype_state != "ACTIVE"
                or locked.latest_version_id != request.subject_version_id
                or not (draft or active)):
            raise ReviewSubjectAccessDenied()

    def require_start_replay_access_in_transaction(
        self, tx: object, *, actor_id: uuid.UUID, review, round_ref,
    ) -> None:
        version_id = getattr(round_ref, "subject_version_id", None)
        if (not self._valid_review(review)
                or not _ids(actor_id, review.project_id,
                            review.subject_id, version_id)
                or getattr(round_ref, "review_id", None) != review.review_id):
            raise ReviewSubjectAccessDenied()
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id,
            prototype_id=review.subject_id,
            prototype_version_id=version_id,
        )
        if (type(locked) is not PrototypeReviewLock
                or locked.prototype_state != "ACTIVE"
                or locked.review_ref != review.review_id):
            raise ReviewSubjectAccessDenied()

    def require_transition_access_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        locked = self._transition_lock(tx, transition)
        if transition.after_progress.state is ReviewRoundState.APPROVED:
            self._qualify_reviewer_ids(
                tx, project_id=transition.before.review.project_id,
                reviewer_ids=transition.after_progress.reviewer_ids,
            )
            self._validate_current(tx, locked)

    def assert_transition_lock_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        self._transition_lock(tx, transition)

    def consume_terminal_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        if not transition.terminal:
            raise ReviewSubjectTransitionError()
        before = self._transition_lock(tx, transition)
        state = self._terminal_version_state(transition)
        self._repo.consume_terminal(
            tx, before=before, transition=transition, version_state=state,
        )
        self._audit.append(tx, AuditEventDraft(
            trace_id=transition.trace_id, event_scope="PROJECT",
            target_project_id=before.snapshot.project_id,
            actor_type="USER", actor_id=transition.actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action="PROTOTYPE_VERSION_" +
                   transition.after_progress.state.value,
            outcome="SUCCESS", target_owner_module="prototype",
            target_object_type="PRT-03",
            target_object_id=transition.before.subject_version_id,
            target_version_id=transition.before.subject_version_id,
            before_state="IN_REVIEW", after_state=state,
        ))

    def assert_terminal_consumed_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        if not transition.terminal:
            raise ReviewSubjectTransitionError()
        self._repo.assert_terminal_consumed(
            tx, transition=transition,
            version_state=self._terminal_version_state(transition),
        )

    def require_transition_replay_access_in_transaction(
        self, tx: object, *, actor_id: uuid.UUID, review, result,
    ) -> None:
        version_id = getattr(result, "subject_version_id", None)
        if (not self._valid_review(review)
                or not _ids(actor_id, review.project_id,
                            review.subject_id, version_id)
                or getattr(result, "review_id", None) != review.review_id):
            raise ReviewSubjectAccessDenied()
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id,
            prototype_id=review.subject_id,
            prototype_version_id=version_id,
        )
        if (type(locked) is not PrototypeReviewLock
                or locked.prototype_state != "ACTIVE"
                or locked.review_ref != review.review_id):
            raise ReviewSubjectAccessDenied()

    def _require_lock(self, tx, request):
        locked = self._repo.lock_subject(
            tx, project_id=request.review.project_id,
            prototype_id=request.review.subject_id,
            prototype_version_id=request.subject_version_id,
        )
        if (type(locked) is not PrototypeReviewLock
                or locked.snapshot.project_id != request.review.project_id
                or locked.snapshot.prototype_id != request.review.subject_id
                or locked.snapshot.prototype_version_id
                   != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        locked.__post_init__()
        return locked

    def _transition_lock(self, tx, transition):
        review = transition.before.review
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id,
            prototype_id=review.subject_id,
            prototype_version_id=transition.before.subject_version_id,
        )
        if (type(locked) is not PrototypeReviewLock
                or locked.prototype_state != "ACTIVE"
                or locked.snapshot.version_state != "IN_REVIEW"
                or locked.review_ref != review.review_id
                or locked.review_round_ref
                   != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        return locked

    def _validate_current(self, tx, locked) -> None:
        try:
            issues = self._current.current_issues(tx, locked.snapshot)
        except Exception:
            raise ReviewSubjectAccessDenied() from None
        if type(issues) is not tuple or issues:
            raise ReviewSubjectAccessDenied()

    def _qualify_reviewer_ids(self, tx, *, project_id, reviewer_ids) -> None:
        try:
            facts = self._reviewers.qualify_in_transaction(
                tx, project_id=project_id, reviewer_ids=reviewer_ids,
                allowed_roles=ALL_MEMBERS,
            )
        except ReviewReviewerEligibilityError:
            raise ReviewSubjectAccessDenied() from None
        if (type(facts) is not tuple or len(facts) != len(reviewer_ids)
                or any(type(fact) is not ProjectReviewerFacts
                       or fact.user_id != user_id
                       or fact.project_id != project_id
                       or fact.project_role not in ALL_MEMBERS
                       for fact, user_id in zip(facts, reviewer_ids))):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _require_request(cls, request) -> None:
        if type(request) is not ReviewSubjectStartRequest:
            raise ReviewSubjectStartError()
        request.__post_init__()
        if not cls._valid_review(request.review):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _require_transition(cls, transition) -> None:
        if type(transition) is not ReviewSubjectTransition:
            raise ReviewSubjectTransitionError()
        transition.__post_init__()
        if not cls._valid_review(transition.before.review):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _valid_review(cls, review) -> bool:
        return (getattr(review, "scope", None) == "PROJECT"
                and _uuid(getattr(review, "project_id", None))
                and getattr(review, "subject_type", None)
                == cls.SUBJECT_TYPE
                and getattr(review, "policy_code", None)
                == cls.POLICY_CODE)

    @staticmethod
    def _terminal_version_state(transition) -> str:
        state = transition.after_progress.state
        if state is ReviewRoundState.APPROVED:
            return "APPROVED"
        if state in (ReviewRoundState.RETURNED,
                     ReviewRoundState.WITHDRAWN):
            return "RETURNED"
        raise ReviewSubjectTransitionError()

    def _now(self) -> datetime:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise ReviewSubjectAccessDenied()
        return now.astimezone(timezone.utc)


def _uuid(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ids(*values: object) -> bool:
    return all(_uuid(value) for value in values)
