"""Handover-owned PROJECT Review Subject facts and terminal consumption."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.task_read import AITaskView
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityItemView, CapabilityVersionView,
)
from plm_assistant.modules.evidence.application.fixed_source_record import (
    LockedEvidenceSource,
)
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ProjectReviewerQualificationService,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.review.application.create_review import (
    AuthorizedReviewCreation, CreatedReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    ReviewBasisObservation,
)
from plm_assistant.modules.review.application.subject_start import (
    PreparedReviewSubject, ReviewSubjectAccessDenied, ReviewSubjectStartError,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition, ReviewSubjectTransitionError,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState

from .create_version import HandoverVersionCreateService
from .source_validation import HandoverSourceValidationError, HandoverSourceValidator
from .validate_version import HandoverVersionSnapshot, HandoverVersionValidationService


@dataclass(frozen=True, slots=True)
class HandoverReviewLock:
    snapshot: HandoverVersionSnapshot
    analysis_state: str
    analysis_lock_version: int
    current_approved_version_ref: uuid.UUID | None
    latest_version_id: uuid.UUID
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    item_states: tuple[tuple[uuid.UUID, str], ...]
    active_action_item_ids: frozenset[uuid.UUID]

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not HandoverVersionSnapshot
                or self.analysis_state not in ("ACTIVE", "ARCHIVED", "RESTRICTED")
                or type(self.analysis_lock_version) is not int
                or self.analysis_lock_version < 0
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
                    or self.review_round_ref.int == 0)
                or type(self.item_states) is not tuple
                or len(self.item_states) != len(self.snapshot.items)
                or any(type(item_id) is not uuid.UUID or item_id.int == 0
                       or state not in ("CANDIDATE", "CONFIRMED")
                       for item_id, state in self.item_states)
                or tuple(item.analysis_item_id for item in self.snapshot.items)
                   != tuple(item_id for item_id, _ in self.item_states)
                or type(self.active_action_item_ids) is not frozenset
                or any(type(item_id) is not uuid.UUID or item_id.int == 0
                       for item_id in self.active_action_item_ids)):
            raise ReviewSubjectStartError()


class HandoverReviewRepositoryPort(Protocol):
    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_id: uuid.UUID, analysis_version_id: uuid.UUID,
    ) -> HandoverReviewLock | None: ...

    def active_analysis_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> bool: ...

    def bind_start(
        self, transaction: object, *, before: HandoverReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None: ...

    def consume_terminal(
        self, transaction: object, *, before: HandoverReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None: ...

    def assert_terminal_consumed(
        self, transaction: object, *, transition: ReviewSubjectTransition,
        version_state: str,
    ) -> None: ...


class HandoverReviewEvidencePort(Protocol):
    def get_for_trace(
        self, transaction: object, *, scope: str,
        project_id: uuid.UUID | None, evidence_id: uuid.UUID,
    ) -> LockedEvidenceSource | None: ...


class HandoverReviewCapabilityPort(Protocol):
    def get_version(self, transaction: object, *, visibility: str,
                    baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> object | None: ...

    def list_items(self, transaction: object, *, visibility: str,
                   baseline_id: uuid.UUID, baseline_version_id: uuid.UUID,
                   after_ordinal: int | None, limit: int) -> tuple[object, ...]: ...


class HandoverReviewAITaskPort(Protocol):
    def get(self, transaction: object, *, ai_task_id: uuid.UUID,
            project_id: uuid.UUID) -> object | None: ...


class HandoverReviewSubjectOwner:
    """Real HND-02 owner for Review identity, start and terminal projection."""

    SUBJECT_TYPE = "HND-02"
    POLICY_CODE = "HANDOVER_ALL_V1"

    def __init__(
        self, *, repository: HandoverReviewRepositoryPort,
        reviewers: ProjectReviewerQualificationService,
        sources: HandoverSourceValidator,
        evidence: HandoverReviewEvidencePort,
        capabilities: HandoverReviewCapabilityPort,
        ai_tasks: HandoverReviewAITaskPort,
        audit, clock=None,
    ) -> None:
        if any(value is None for value in (
                repository, reviewers, sources, evidence, capabilities,
                ai_tasks, audit)):
            raise ValueError("Handover Review Subject dependencies required")
        self._repo, self._reviewers = repository, reviewers
        self._sources, self._evidence = sources, evidence
        self._capabilities, self._ai_tasks = capabilities, ai_tasks
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def authorize_create(
        self, tx: object, *, user_id: uuid.UUID, project_id: uuid.UUID,
        subject_type: str, subject_id: uuid.UUID,
        subject_version_id: uuid.UUID,
    ) -> AuthorizedReviewCreation | None:
        if (not self._ids(user_id, project_id, subject_id, subject_version_id)
                or subject_type != self.SUBJECT_TYPE):
            return None
        locked = self._repo.lock_subject(
            tx, project_id=project_id, analysis_id=subject_id,
            analysis_version_id=subject_version_id,
        )
        if (type(locked) is not HandoverReviewLock
                or locked.analysis_state != "ACTIVE"
                or locked.snapshot.project_id != project_id
                or locked.snapshot.handover_analysis_id != subject_id
                or locked.snapshot.handover_analysis_version_id
                   != subject_version_id
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
                or not self._ids(user_id, review.project_id, review.subject_id)
                or review.subject_type != self.SUBJECT_TYPE
                or review.policy_code != self.POLICY_CODE):
            return False
        return self._repo.active_analysis_exists(
            tx, project_id=review.project_id, analysis_id=review.subject_id,
        ) is True

    def prepare_start_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> PreparedReviewSubject:
        self._require_request(request)
        self._qualify_reviewers(tx, request)
        locked = self._require_lock(tx, request)
        if (locked.analysis_state != "ACTIVE"
                or locked.snapshot.version_state != "DRAFT"
                or locked.review_ref is not None
                or locked.latest_version_id != request.subject_version_id
                or any(state != "CANDIDATE"
                       for _, state in locked.item_states)):
            raise ReviewSubjectAccessDenied()
        basis = self._validate_current(tx, locked)
        now = self._now()
        return PreparedReviewSubject(
            request, locked.snapshot.content_fingerprint, 1, now,
            request.reviewer_ids, basis,
        )

    def finalize_start_in_transaction(
        self, tx: object, request: ReviewSubjectStartRequest,
    ) -> None:
        self._require_request(request)
        locked = self._require_lock(tx, request)
        if (locked.analysis_state != "ACTIVE"
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
        if (locked.analysis_state != "ACTIVE"
                or locked.latest_version_id != request.subject_version_id
                or not (draft or active)):
            raise ReviewSubjectAccessDenied()

    def require_start_replay_access_in_transaction(
        self, tx: object, *, actor_id: uuid.UUID, review, round_ref,
    ) -> None:
        if (not self._valid_review(review)
                or not self._ids(actor_id, review.project_id,
                                 review.subject_id)
                or getattr(round_ref, "review_id", None) != review.review_id
                or type(getattr(round_ref, "subject_version_id", None))
                   is not uuid.UUID):
            raise ReviewSubjectAccessDenied()
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id,
            analysis_id=review.subject_id,
            analysis_version_id=round_ref.subject_version_id,
        )
        if (type(locked) is not HandoverReviewLock
                or locked.analysis_state != "ACTIVE"
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
        review_state = transition.after_progress.state.value
        self._audit.append(tx, AuditEventDraft(
            trace_id=transition.trace_id, event_scope="PROJECT",
            target_project_id=before.snapshot.project_id,
            actor_type="USER", actor_id=transition.actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action="HND_VERSION_" + review_state, outcome="SUCCESS",
            target_owner_module="handover", target_object_type="HND-02",
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
                or not self._ids(actor_id, review.project_id,
                                 review.subject_id, version_id)
                or getattr(result, "review_id", None) != review.review_id):
            raise ReviewSubjectAccessDenied()
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id,
            analysis_id=review.subject_id,
            analysis_version_id=version_id,
        )
        if (type(locked) is not HandoverReviewLock
                or locked.analysis_state != "ACTIVE"
                or locked.review_ref != review.review_id):
            raise ReviewSubjectAccessDenied()

    def _require_lock(self, tx, request):
        locked = self._repo.lock_subject(
            tx, project_id=request.review.project_id,
            analysis_id=request.review.subject_id,
            analysis_version_id=request.subject_version_id,
        )
        if (type(locked) is not HandoverReviewLock
                or locked.snapshot.project_id != request.review.project_id
                or locked.snapshot.handover_analysis_id
                   != request.review.subject_id
                or locked.snapshot.handover_analysis_version_id
                   != request.subject_version_id):
            raise ReviewSubjectAccessDenied()
        locked.__post_init__()
        return locked

    def _transition_lock(self, tx, transition):
        review = transition.before.review
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id,
            analysis_id=review.subject_id,
            analysis_version_id=transition.before.subject_version_id,
        )
        if (type(locked) is not HandoverReviewLock
                or locked.analysis_state != "ACTIVE"
                or locked.snapshot.version_state != "IN_REVIEW"
                or locked.review_ref != review.review_id
                or locked.review_round_ref
                   != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        return locked

    def _validate_current(
        self, tx: object, locked: HandoverReviewLock,
    ) -> tuple[ReviewBasisObservation, ...]:
        snapshot = locked.snapshot
        payload = HandoverVersionValidationService._snapshot_payload(snapshot)
        if not hmac.compare_digest(
                canonical_payload_fingerprint(payload),
                snapshot.content_fingerprint):
            raise ReviewSubjectAccessDenied()
        try:
            sources = self._sources.validate(
                tx, project_id=snapshot.project_id,
                references=snapshot.source_documents,
            )
        except HandoverSourceValidationError:
            raise ReviewSubjectAccessDenied() from None
        if sources.source_set_ref != snapshot.source_set_ref:
            raise ReviewSubjectAccessDenied()
        source_pairs = {(item.document_id, item.document_version_id)
                        for item in snapshot.source_documents}
        observations: dict[uuid.UUID, ReviewBasisObservation] = {}
        now = self._now()
        stable: set[uuid.UUID] = set()
        for item in snapshot.items:
            try:
                HandoverVersionCreateService._validate_item(item, stable)
            except Exception:
                raise ReviewSubjectAccessDenied() from None
            stable.add(item.analysis_item_id)
            if ((item.source_missing or item.item_type == "NEED_CONFIRM")
                    and item.analysis_item_id
                    not in locked.active_action_item_ids):
                raise ReviewSubjectAccessDenied()
            for evidence_id in item.evidence_refs:
                source = self._evidence.get_for_trace(
                    tx, scope="PROJECT", project_id=snapshot.project_id,
                    evidence_id=evidence_id,
                )
                if (type(source) is not LockedEvidenceSource
                        or source.scope != "PROJECT"
                        or source.project_id != snapshot.project_id
                        or (source.document_id, source.document_version_id)
                           not in source_pairs
                        or type(source.content_fingerprint) is not bytes
                        or len(source.content_fingerprint) != 32
                        or type(source.lock_version) is not int
                        or source.lock_version < 0):
                    raise ReviewSubjectAccessDenied()
                observation = ReviewBasisObservation(
                    "EVIDENCE", evidence_id, "PROJECT", snapshot.project_id,
                    "ELIGIBLE", source.lock_version,
                    source.content_fingerprint, now,
                )
                previous = observations.setdefault(evidence_id, observation)
                if previous != observation:
                    raise ReviewSubjectAccessDenied()
        try:
            version = self._capabilities.get_version(
                tx, visibility="CURRENT_APPROVED",
                baseline_id=snapshot.capability_baseline_id,
                baseline_version_id=snapshot.capability_baseline_version_ref,
            )
            capability_items = self._capabilities.list_items(
                tx, visibility="CURRENT_APPROVED",
                baseline_id=snapshot.capability_baseline_id,
                baseline_version_id=snapshot.capability_baseline_version_ref,
                after_ordinal=None, limit=501,
            )
        except Exception:
            raise ReviewSubjectAccessDenied() from None
        allowed = {item.capability_item_id for item in capability_items
                   if type(item) is CapabilityItemView
                   and item.state == "AVAILABLE"}
        if (type(version) is not CapabilityVersionView
                or version.baseline_id != snapshot.capability_baseline_id
                or version.baseline_version_id
                   != snapshot.capability_baseline_version_ref
                or version.state != "APPROVED"
                or len(capability_items)
                   != version.declared_item_count
                or len(capability_items) > 500
                or any(type(item) is not CapabilityItemView
                       for item in capability_items)
                or any(ref.capability_item_id not in allowed
                       for item in snapshot.items
                       for ref in item.capability_refs)):
            raise ReviewSubjectAccessDenied()
        for task_id in snapshot.ai_task_refs:
            task = self._ai_tasks.get(
                tx, ai_task_id=task_id, project_id=snapshot.project_id,
            )
            if (type(task) is not AITaskView
                    or task.task_type != "GAP_ANALYSIS"
                    or task.task_state != "SUCCEEDED"):
                raise ReviewSubjectAccessDenied()
        return tuple(observations[key]
                     for key in sorted(observations, key=str))

    def _qualify_reviewers(self, tx, request):
        self._qualify_reviewer_ids(
            tx, project_id=request.review.project_id,
            reviewer_ids=request.reviewer_ids,
        )

    def _qualify_reviewer_ids(self, tx, *, project_id, reviewer_ids):
        try:
            facts = self._reviewers.qualify_in_transaction(
                tx, project_id=project_id,
                reviewer_ids=reviewer_ids,
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
        return (getattr(review, "scope", None) == "PROJECT"
                and type(getattr(review, "project_id", None)) is uuid.UUID
                and getattr(review, "subject_type", None) == cls.SUBJECT_TYPE
                and getattr(review, "policy_code", None) == cls.POLICY_CODE)

    @staticmethod
    def _terminal_version_state(transition):
        state = transition.after_progress.state
        if state is ReviewRoundState.APPROVED:
            return "APPROVED"
        if state in (ReviewRoundState.RETURNED, ReviewRoundState.WITHDRAWN):
            return "RETURNED"
        raise ReviewSubjectTransitionError()

    @staticmethod
    def _ids(*values):
        return all(type(value) is uuid.UUID and value.int != 0
                   for value in values)

    def _now(self):
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise ReviewSubjectAccessDenied()
        return now.astimezone(timezone.utc)
