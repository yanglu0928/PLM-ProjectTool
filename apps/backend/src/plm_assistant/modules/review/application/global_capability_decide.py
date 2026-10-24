"""Idempotent CAP-01 GLOBAL reviewer decision in the Review/Capability transaction."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)

from .global_persistence import (
    AppliedGlobalReviewTransitionRef, GlobalReviewPersistenceService,
)
from .persist_round import ReviewRoundPersistError
from .read_snapshot import FixedReviewRoundSnapshot
from .subject_start import ReviewSubjectAccessDenied
from ..domain.round_progress import ReviewDecisionKind


class GlobalCapabilityReviewDecisionError(RuntimeError):
    def __init__(self, code: str = "GLOBAL_REVIEW_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DecideGlobalCapabilityReview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    review_id: uuid.UUID
    round_id: uuid.UUID
    decision: ReviewDecisionKind
    comment: str | None = field(repr=False)
    idempotency_key: str = field(repr=False)


class _AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class _LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class _RepositoryPort(Protocol):
    def lock_global_transition_context(self, transaction: object, *,
                                       review_id: uuid.UUID, round_id: uuid.UUID
                                       ) -> FixedReviewRoundSnapshot | None: ...
    def get_global_transition_ref(self, transaction: object, *, review_id: uuid.UUID,
                                  round_id: uuid.UUID, event_id: uuid.UUID
                                  ) -> AppliedGlobalReviewTransitionRef | None: ...


class _ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class _SubjectPort(Protocol):
    def require_transition_replay_access_in_transaction(
        self, transaction: object, *, actor_id: uuid.UUID,
        review: object, result: object,
    ) -> None: ...


class GlobalCapabilityReviewDecisionService:
    OPERATION = "V1_GLOBAL_CAP_REVIEW_DECIDE"
    RESULT = "V1_GLOBAL_CAP_REVIEW_TRANSITION"

    def __init__(self, *, unit_of_work: Callable[[], object], access: _AccessPort,
                 license_guard: _LicensePort, repository: _RepositoryPort,
                 receipts: _ReceiptPort, reviews: GlobalReviewPersistenceService,
                 subject: _SubjectPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, repository, receipts,
                reviews, subject)):
            raise ValueError("GLOBAL Capability Review decision dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repository, self._receipts = repository, receipts
        self._reviews, self._subject = reviews, subject
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def decide(self, command: DecideGlobalCapabilityReview) -> AppliedGlobalReviewTransitionRef:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "review_id": str(command.review_id), "round_id": str(command.round_id),
                "decision": command.decision.value, "comment": command.comment,
            })
            with self._uow() as tx:
                self._require_reviewer(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_reviewer(tx, command)
                fixed = self._repository.lock_global_transition_context(
                    tx, review_id=command.review_id, round_id=command.round_id,
                )
                if fixed is None:
                    raise GlobalCapabilityReviewDecisionError("RESOURCE_NOT_FOUND")
                if (type(fixed) is not FixedReviewRoundSnapshot
                        or fixed.review.scope != "GLOBAL" or fixed.review.project_id is not None
                        or fixed.review.review_id != command.review_id
                        or fixed.review.subject_type != "CAP-01"
                        or fixed.review.policy_code != "DEPLOYMENT_ALL_V1"
                        or fixed.progress.round_id != command.round_id):
                    raise GlobalCapabilityReviewDecisionError("RESOURCE_NOT_FOUND")
                fixed.__post_init__()
                if actor not in fixed.progress.reviewer_ids:
                    raise GlobalCapabilityReviewDecisionError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None,
                    operation=self.OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    return self._replay(tx, command, actor, fixed, replay)
                result = self._reviews.decide_in_transaction(
                    tx, actor_id=actor, review_id=command.review_id,
                    round_id=command.round_id, trace_id=command.trace_id,
                    decision=command.decision, comment=command.comment,
                )
                if (type(result) is not AppliedGlobalReviewTransitionRef
                        or result.review_id != command.review_id
                        or result.round_id != command.round_id
                        or result.subject_version_id != fixed.subject_version_id
                        or result.actor_id != actor or result.action != "DECIDE"):
                    raise GlobalCapabilityReviewDecisionError()
                result.__post_init__()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    self.RESULT, result.event_id, 200,
                ))
                tx.commit()
                return result
        except GlobalCapabilityReviewDecisionError:
            raise
        except RuntimeLicenseError:
            raise GlobalCapabilityReviewDecisionError("LICENSE_OPERATION_DENIED") from None
        except ReviewSubjectAccessDenied:
            raise GlobalCapabilityReviewDecisionError("RESOURCE_NOT_FOUND") from None
        except (IdempotencyError, ReviewRoundPersistError) as exc:
            raise GlobalCapabilityReviewDecisionError(exc.code) from None
        except Exception:
            raise GlobalCapabilityReviewDecisionError() from None

    def _replay(self, tx: object, command: DecideGlobalCapabilityReview,
                actor: uuid.UUID, fixed: FixedReviewRoundSnapshot,
                replay: IdempotencyResult) -> AppliedGlobalReviewTransitionRef:
        if (type(replay) is not IdempotencyResult
                or replay.ref_type != self.RESULT or replay.status_code != 200):
            raise GlobalCapabilityReviewDecisionError()
        result = self._repository.get_global_transition_ref(
            tx, review_id=command.review_id, round_id=command.round_id,
            event_id=replay.ref_id,
        )
        if (type(result) is not AppliedGlobalReviewTransitionRef
                or result.event_id != replay.ref_id
                or result.review_id != command.review_id
                or result.round_id != command.round_id
                or result.subject_version_id != fixed.subject_version_id
                or result.actor_id != actor or result.action != "DECIDE"):
            raise GlobalCapabilityReviewDecisionError()
        result.__post_init__()
        if self._subject.require_transition_replay_access_in_transaction(
                tx, actor_id=actor, review=fixed.review, result=result) is not None:
            raise GlobalCapabilityReviewDecisionError("RESOURCE_NOT_FOUND")
        return result

    def _require_reviewer(self, tx: object, command: DecideGlobalCapabilityReview) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise GlobalCapabilityReviewDecisionError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise GlobalCapabilityReviewDecisionError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _validate(command: DecideGlobalCapabilityReview) -> None:
        if (type(command) is not DecideGlobalCapabilityReview
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or not value.int for value in (
                    command.trace_id, command.review_id, command.round_id,
                ))
                or type(command.decision) is not ReviewDecisionKind
                or command.comment is not None and (
                    type(command.comment) is not str or "\x00" in command.comment)
                or command.decision is ReviewDecisionKind.RETURN
                and (command.comment is None or not command.comment.strip())):
            raise GlobalCapabilityReviewDecisionError("VALIDATION_FAILED")
