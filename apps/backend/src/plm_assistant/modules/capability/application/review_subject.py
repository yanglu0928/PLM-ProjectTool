"""Capability-owned Review Subject facts and persistent start lock."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.evidence.application.fixed_source_record import (
    LockedEvidenceSource,
)
from plm_assistant.modules.review.application.read_snapshot import (
    ReviewBasisObservation,
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

from .create_version import CapabilityItemDraft
from .source_validation import (
    CapabilityDocumentRef,
    CapabilitySourceValidationError,
    CapabilitySourceValidator,
)
from .validate_version import CapabilityVersionSnapshot


@dataclass(frozen=True, slots=True)
class CapabilityReviewLock:
    snapshot: CapabilityVersionSnapshot
    baseline_state: str
    baseline_lock_version: int
    current_approved_version_ref: uuid.UUID | None
    latest_version_id: uuid.UUID
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not CapabilityVersionSnapshot
                or self.baseline_state not in (
                    "ACTIVE", "ARCHIVED", "RESTRICTED",
                )
                or type(self.baseline_lock_version) is not int
                or self.baseline_lock_version < 0
                or type(self.latest_version_id) is not uuid.UUID
                or self.latest_version_id.int == 0
                or self.current_approved_version_ref is not None
                and (type(self.current_approved_version_ref) is not uuid.UUID
                     or self.current_approved_version_ref.int == 0)
                or (self.review_ref is None) != (self.review_round_ref is None)
                or self.review_ref is not None and (
                    type(self.review_ref) is not uuid.UUID
                    or self.review_ref.int == 0
                    or type(self.review_round_ref) is not uuid.UUID
                    or self.review_round_ref.int == 0)):
            raise ReviewSubjectStartError()


class CapabilityReviewRepositoryPort(Protocol):
    def lock_subject(
        self, transaction: object, *, baseline_id: uuid.UUID,
        baseline_version_id: uuid.UUID,
    ) -> CapabilityReviewLock | None: ...

    def bind_start(
        self, transaction: object, *, before: CapabilityReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None: ...

    def consume_terminal(
        self, transaction: object, *, before: CapabilityReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None: ...

    def assert_terminal_consumed(
        self, transaction: object, *, transition: ReviewSubjectTransition,
        version_state: str,
    ) -> None: ...


class CapabilityReviewUserPort(Protocol):
    def current_enabled_user(
        self, transaction: object, *, user_id: uuid.UUID,
    ) -> CurrentUserFacts | None: ...


class CapabilityReviewEvidencePort(Protocol):
    def get_for_trace(
        self, transaction: object, *, scope: str,
        project_id: uuid.UUID | None, evidence_id: uuid.UUID,
    ) -> LockedEvidenceSource | None: ...


class CapabilityReviewSubjectOwner:
    """Real CAP-01 owner for Review start, access and terminal consumption."""

    SUBJECT_TYPE = "CAP-01"
    POLICY_CODE = "DEPLOYMENT_ALL_V1"

    def __init__(
        self, *, users: CapabilityReviewUserPort,
        repository: CapabilityReviewRepositoryPort,
        sources: CapabilitySourceValidator,
        evidence: CapabilityReviewEvidencePort,
        audit,
        terminal_enabled: bool = True,
        clock=None,
    ) -> None:
        if any(item is None for item in (
                users, repository, sources, evidence, audit)):
            raise ValueError("Capability Review Subject dependencies required")
        self._users, self._repo = users, repository
        self._sources, self._evidence = sources, evidence
        self._audit = audit
        if type(terminal_enabled) is not bool:
            raise ValueError("Capability terminal policy is invalid")
        self._terminal_enabled = terminal_enabled
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prepare_start_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> PreparedReviewSubject:
        self._require_request(request)
        self._require_users(
            tx, actor_id=request.actor_id,
            reviewer_ids=request.reviewer_ids, actor_must_admin=True,
        )
        locked = self._require_lock(tx, request)
        if (locked.baseline_state != "ACTIVE"
                or locked.snapshot.version_state != "DRAFT"
                or locked.review_ref is not None
                or locked.review_round_ref is not None
                or locked.latest_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        basis = self._validate_sources(tx, locked.snapshot)
        now = self._now()
        return PreparedReviewSubject(
            request, locked.snapshot.content_fingerprint, 1, now,
            request.reviewer_ids, basis,
        )

    def finalize_start_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> None:
        self._require_request(request)
        self._require_users(
            tx, actor_id=request.actor_id,
            reviewer_ids=request.reviewer_ids, actor_must_admin=True,
        )
        locked = self._require_lock(tx, request)
        if (locked.baseline_state != "ACTIVE"
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
        if (locked.baseline_state != "ACTIVE"
                or locked.latest_version_id != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        draft = (locked.snapshot.version_state == "DRAFT"
                 and locked.review_ref is None
                 and locked.review_round_ref is None)
        active = (locked.snapshot.version_state == "IN_REVIEW"
                  and locked.review_ref == request.review.review_id
                  and locked.review_round_ref == request.round_id)
        if not (draft or active):
            raise ReviewSubjectAccessDenied()

    def require_start_replay_access_in_transaction(
        self, tx: object, *, actor_id: uuid.UUID,
        review, round_ref,
    ) -> None:
        if (not self._valid_review(review)
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or getattr(round_ref, "review_id", None) != review.review_id
                or getattr(round_ref, "subject_version_id", None) is None):
            raise ReviewSubjectAccessDenied()
        self._require_users(
            tx, actor_id=actor_id, reviewer_ids=(), actor_must_admin=True,
        )
        locked = self._repo.lock_subject(
            tx, baseline_id=review.subject_id,
            baseline_version_id=round_ref.subject_version_id,
        )
        if (type(locked) is not CapabilityReviewLock
                or locked.review_ref != review.review_id):
            raise ReviewSubjectAccessDenied()

    def require_transition_access_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        withdrawal = transition.after_progress.withdrawal is not None
        self._require_users(
            tx, actor_id=transition.actor_id,
            reviewer_ids=(transition.after_progress.reviewer_ids
                          if transition.terminal else ()),
            actor_must_admin=withdrawal,
        )
        locked = self._transition_lock(tx, transition)
        if transition.terminal:
            self._validate_sources(tx, locked.snapshot)

    def assert_transition_lock_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        self._transition_lock(tx, transition)

    def consume_terminal_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        if not self._terminal_enabled or not transition.terminal:
            raise ReviewSubjectTransitionError()
        before = self._transition_lock(tx, transition)
        state = self._terminal_version_state(transition)
        self._repo.consume_terminal(
            tx, before=before, transition=transition, version_state=state,
        )
        review_state = transition.after_progress.state.value
        self._audit.append(tx, AuditEventDraft(
            trace_id=transition.trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER",
            actor_id=transition.actor_id, original_actor_id=None,
            actor_hint_digest=None, action="CAP_VERSION_" + review_state,
            outcome="SUCCESS", target_owner_module="capability",
            target_object_type="CAP-02",
            target_object_id=transition.before.subject_version_id,
            target_version_id=transition.before.subject_version_id,
            before_state="IN_REVIEW", after_state=state,
        ))

    def assert_terminal_consumed_in_transaction(
        self, tx: object, transition: ReviewSubjectTransition,
    ) -> None:
        self._require_transition(transition)
        if not self._terminal_enabled or not transition.terminal:
            raise ReviewSubjectTransitionError()
        self._repo.assert_terminal_consumed(
            tx, transition=transition,
            version_state=self._terminal_version_state(transition),
        )

    def require_transition_replay_access_in_transaction(
        self, tx: object, *, actor_id: uuid.UUID, review, result,
    ) -> None:
        if (not self._valid_review(review)
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or getattr(result, "review_id", None) != review.review_id
                or getattr(result, "subject_version_id", None) is None):
            raise ReviewSubjectAccessDenied()
        self._require_users(
            tx, actor_id=actor_id, reviewer_ids=(), actor_must_admin=False,
        )
        locked = self._repo.lock_subject(
            tx, baseline_id=review.subject_id,
            baseline_version_id=result.subject_version_id,
        )
        if (type(locked) is not CapabilityReviewLock
                or locked.review_ref != review.review_id):
            raise ReviewSubjectAccessDenied()

    def _require_lock(self, tx, request):
        locked = self._repo.lock_subject(
            tx, baseline_id=request.review.subject_id,
            baseline_version_id=request.subject_version_id,
        )
        if (type(locked) is not CapabilityReviewLock
                or locked.snapshot.baseline_id != request.review.subject_id
                or locked.snapshot.baseline_version_id
                   != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        locked.__post_init__()
        return locked

    def _transition_lock(self, tx, transition):
        locked = self._repo.lock_subject(
            tx, baseline_id=transition.before.review.subject_id,
            baseline_version_id=transition.before.subject_version_id,
        )
        if (type(locked) is not CapabilityReviewLock
                or locked.baseline_state != "ACTIVE"
                or locked.snapshot.version_state != "IN_REVIEW"
                or locked.review_ref != transition.before.review.review_id
                or locked.review_round_ref
                   != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        return locked

    def _validate_sources(
        self, tx: object, snapshot: CapabilityVersionSnapshot,
    ) -> tuple[ReviewBasisObservation, ...]:
        documents = self._unique_documents(snapshot.items)
        try:
            source_set = self._sources.validate(tx, documents)
        except CapabilitySourceValidationError:
            raise ReviewSubjectAccessDenied() from None
        if not hmac.compare_digest(
                source_set.source_collection_ref,
                snapshot.source_collection_ref):
            raise ReviewSubjectAccessDenied()
        observed: dict[uuid.UUID, ReviewBasisObservation] = {}
        now = self._now()
        for item in snapshot.items:
            pairs = {(ref.document_id, ref.document_version_id)
                     for ref in item.document_refs}
            for evidence_id in item.evidence_refs:
                source = self._evidence.get_for_trace(
                    tx, scope="GLOBAL", project_id=None,
                    evidence_id=evidence_id,
                )
                if (type(source) is not LockedEvidenceSource
                        or source.evidence_id != evidence_id
                        or source.scope != "GLOBAL"
                        or source.project_id is not None
                        or (source.document_id,
                            source.document_version_id) not in pairs
                        or type(source.content_fingerprint) is not bytes
                        or len(source.content_fingerprint) != 32
                        or type(source.lock_version) is not int
                        or source.lock_version < 0):
                    raise ReviewSubjectAccessDenied()
                current = ReviewBasisObservation(
                    "EVIDENCE", evidence_id, "GLOBAL", None, "ELIGIBLE",
                    source.lock_version, source.content_fingerprint, now,
                )
                previous = observed.setdefault(evidence_id, current)
                if previous != current:
                    raise ReviewSubjectAccessDenied()
        return tuple(observed[key] for key in sorted(observed, key=str))

    @staticmethod
    def _terminal_version_state(transition: ReviewSubjectTransition) -> str:
        state = transition.after_progress.state
        if state is ReviewRoundState.APPROVED:
            return "APPROVED"
        if state in (ReviewRoundState.RETURNED, ReviewRoundState.WITHDRAWN):
            return "RETURNED"
        raise ReviewSubjectTransitionError()

    def _require_users(
        self, tx, *, actor_id, reviewer_ids, actor_must_admin,
    ) -> None:
        if type(reviewer_ids) is not tuple:
            raise ReviewSubjectAccessDenied()
        found = {}
        for user_id in sorted(set((actor_id,) + reviewer_ids)):
            facts = self._users.current_enabled_user(tx, user_id=user_id)
            if (type(facts) is not CurrentUserFacts
                    or facts.user_id != user_id):
                raise ReviewSubjectAccessDenied()
            found[user_id] = facts
        if (actor_id not in found
                or actor_must_admin
                and found[actor_id].deployment_role != "DEPLOYMENT_ADMIN"):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _require_request(cls, request):
        if type(request) is not ReviewSubjectStartRequest:
            raise ReviewSubjectStartError()
        request.__post_init__()
        if not cls._valid_review(request.review):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _require_transition(cls, transition):
        if type(transition) is not ReviewSubjectTransition:
            raise ReviewSubjectTransitionError()
        transition.__post_init__()
        if not cls._valid_review(transition.before.review):
            raise ReviewSubjectAccessDenied()

    @classmethod
    def _valid_review(cls, review):
        return (getattr(review, "scope", None) == "GLOBAL"
                and getattr(review, "project_id", None) is None
                and getattr(review, "subject_type", None) == cls.SUBJECT_TYPE
                and getattr(review, "policy_code", None) == cls.POLICY_CODE)

    @staticmethod
    def _unique_documents(
        items: tuple[CapabilityItemDraft, ...],
    ) -> tuple[CapabilityDocumentRef, ...]:
        found: dict[uuid.UUID, CapabilityDocumentRef] = {}
        for item in items:
            for reference in item.document_refs:
                previous = found.setdefault(
                    reference.document_version_id, reference,
                )
                if previous.document_id != reference.document_id:
                    raise ReviewSubjectAccessDenied()
        return tuple(sorted(found.values(),
                            key=lambda value: str(value.document_version_id)))

    def _now(self):
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise ReviewSubjectAccessDenied()
        return now.astimezone(timezone.utc)
