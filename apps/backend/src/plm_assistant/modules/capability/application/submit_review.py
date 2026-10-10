"""Idempotent Capability Version submission into the trusted GLOBAL Review kernel."""

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
from plm_assistant.modules.review.application.global_persistence import (
    GlobalReviewPersistenceService, PersistedGlobalReviewSubmission,
    SubmittedGlobalReviewRef,
)
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectStartError,
)


class CapabilityReviewSubmissionError(RuntimeError):
    def __init__(self, code: str = "SYSTEM_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SubmitCapabilityVersionReview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    baseline_version_id: uuid.UUID
    reviewer_ids: tuple[uuid.UUID, ...]
    policy_ref: str
    idempotency_key: str = field(repr=False)


class CapabilityReviewAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class CapabilityReviewLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CapabilityReviewReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CapabilityReviewReplayPort(Protocol):
    def get_global_submission(self, transaction: object, *,
                              round_id: uuid.UUID
                              ) -> PersistedGlobalReviewSubmission | None: ...


class CapabilityReviewReplaySubjectPort(Protocol):
    def require_start_replay_access_in_transaction(
        self, transaction: object, *, actor_id: uuid.UUID,
        review: object, round_ref: object,
    ) -> None: ...


class CapabilityReviewSubmissionService:
    POLICY_REF = "DEPLOYMENT_ALL_V1"

    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: CapabilityReviewAccessPort,
                 license_guard: CapabilityReviewLicensePort,
                 receipts: CapabilityReviewReceiptPort,
                 replay_repository: CapabilityReviewReplayPort,
                 reviews: GlobalReviewPersistenceService,
                 subjects: CapabilityReviewReplaySubjectPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, receipts,
                replay_repository, reviews, subjects)):
            raise ValueError("Capability Review submission dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._receipts, self._replays = receipts, replay_repository
        self._reviews, self._subjects = reviews, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(self, command: SubmitCapabilityVersionReview) -> SubmittedGlobalReviewRef:
        reviewers = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "baseline_id": str(command.baseline_id),
                "baseline_version_id": str(command.baseline_version_id),
                "reviewer_ids": [str(value) for value in reviewers],
                "policy_ref": command.policy_ref,
            })
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None,
                    operation="V1_CAP_VERSION_SUBMIT_REVIEW",
                    key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    result = self._replay(
                        tx, actor, command, reviewers, replay,
                    )
                    return result
                result = self._reviews.submit_in_transaction(
                    tx, actor_id=actor, subject_type="CAP-01",
                    subject_id=command.baseline_id,
                    subject_version_id=command.baseline_version_id,
                    reviewer_ids=reviewers, policy_code=command.policy_ref,
                    trace_id=command.trace_id,
                )
                self._validate_result(result, command, reviewers, actor)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_CAP_VERSION_REVIEW_SUBMISSION", result.round_id, 201,
                ))
                tx.commit()
                return result
        except CapabilityReviewSubmissionError:
            raise
        except RuntimeLicenseError:
            raise CapabilityReviewSubmissionError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise CapabilityReviewSubmissionError(exc.code) from None
        except ReviewSubjectAccessDenied:
            raise CapabilityReviewSubmissionError("BUSINESS_REVIEW_NOT_ELIGIBLE") from None
        except ReviewSubjectStartError:
            raise CapabilityReviewSubmissionError("VALIDATION_FAILED") from None
        except ReviewRoundPersistError as exc:
            mapped = {
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise CapabilityReviewSubmissionError(mapped) from None
        except Exception:
            raise CapabilityReviewSubmissionError() from None

    def _replay(self, tx: object, actor: uuid.UUID,
                command: SubmitCapabilityVersionReview,
                reviewers: tuple[uuid.UUID, ...],
                receipt: IdempotencyResult) -> SubmittedGlobalReviewRef:
        if (type(receipt) is not IdempotencyResult
                or receipt.ref_type != "V1_CAP_VERSION_REVIEW_SUBMISSION"
                or receipt.status_code != 201):
            raise CapabilityReviewSubmissionError()
        persisted = self._replays.get_global_submission(
            tx, round_id=receipt.ref_id,
        )
        if type(persisted) is not PersistedGlobalReviewSubmission:
            raise CapabilityReviewSubmissionError()
        persisted.__post_init__()
        result = persisted.submission
        self._validate_result(result, command, reviewers, actor)
        if result.round_id != receipt.ref_id:
            raise CapabilityReviewSubmissionError()
        self._subjects.require_start_replay_access_in_transaction(
            tx, actor_id=actor, review=persisted.review, round_ref=result,
        )
        return result

    @classmethod
    def _validate(cls, command: SubmitCapabilityVersionReview
                  ) -> tuple[uuid.UUID, ...]:
        if (type(command) is not SubmitCapabilityVersionReview
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.baseline_id,
                    command.baseline_version_id,
                ))
                or type(command.reviewer_ids) is not tuple
                or not 1 <= len(command.reviewer_ids) <= 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in command.reviewer_ids)
                or len(set(command.reviewer_ids)) != len(command.reviewer_ids)
                or command.policy_ref != cls.POLICY_REF):
            raise CapabilityReviewSubmissionError("VALIDATION_FAILED")
        return tuple(sorted(command.reviewer_ids, key=str))

    @staticmethod
    def _validate_result(result: object, command: SubmitCapabilityVersionReview,
                         reviewers: tuple[uuid.UUID, ...], actor: uuid.UUID) -> None:
        if (type(result) is not SubmittedGlobalReviewRef
                or result.subject_type != "CAP-01"
                or result.subject_id != command.baseline_id
                or result.subject_version_id != command.baseline_version_id
                or result.policy_code != command.policy_ref
                or result.reviewer_ids != reviewers
                or result.submitted_by != actor
                or result.round_no != 1
                or result.review_after_version != 1):
            raise CapabilityReviewSubmissionError()
        result.__post_init__()

    def _require_admin(self, tx: object,
                       command: SubmitCapabilityVersionReview) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise CapabilityReviewSubmissionError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise CapabilityReviewSubmissionError("AUTH_ACCESS_DENIED")
        return actor
