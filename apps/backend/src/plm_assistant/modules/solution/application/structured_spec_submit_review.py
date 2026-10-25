"""Atomic SOL-06 submission into the PROJECT Review kernel."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.persist_round import (
    ReviewRoundPersistError,
)
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission,
    ProjectReviewPersistenceService,
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
    ReviewSubjectProofContext,
    ReviewSubjectStartError,
)


_OPERATION = "V1_SOL_SPEC_SUBMIT_REVIEW"
_RESULT_TYPE = "V1_SOL_SPEC_REVIEW_SUBMISSION"


class StructuredSpecReviewSubmissionError(RuntimeError):
    def __init__(self, code: str = "SYSTEM_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class _RetryStructuredSpecReviewDeadlock(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitStructuredSpecReview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    structured_solution_spec_id: uuid.UUID
    reviewer_ids: tuple[uuid.UUID, ...]
    policy_ref: str
    idempotency_key: str = field(repr=False)


class StructuredSpecReviewSubmissionAccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class StructuredSpecReviewSubmissionReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class StructuredSpecReviewSubmissionReplayPort(Protocol):
    def get_project_submission(
        self, transaction: object, *, project_id: uuid.UUID,
        round_id: uuid.UUID,
    ) -> PersistedProjectReviewSubmission | None: ...

    def is_retryable_deadlock(self, error: Exception) -> bool: ...


class StructuredSpecReviewIdentityPort(Protocol):
    def series_for_version(
        self, transaction: object, *, project_id: uuid.UUID,
        spec_id: uuid.UUID,
    ) -> uuid.UUID | None: ...


class StructuredSpecReviewSubmissionService:
    POLICY_REF = "STRUCTURED_SPEC_ALL_V1"

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: StructuredSpecReviewSubmissionAccessPort,
        license_guard: object, authorization: ProjectAuthorizationService,
        reviewers: ProjectReviewerQualificationService,
        receipts: StructuredSpecReviewSubmissionReceiptPort,
        replay_repository: StructuredSpecReviewSubmissionReplayPort,
        identity: StructuredSpecReviewIdentityPort,
        reviews: ProjectReviewPersistenceService, subjects: object,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, reviewers,
                receipts, replay_repository, identity, reviews, subjects)):
            raise ValueError(
                "Structured spec Review submission dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._reviewers = authorization, reviewers
        self._receipts, self._replays, self._identity = (
            receipts, replay_repository, identity)
        self._reviews, self._subjects = reviews, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(
        self, command: SubmitStructuredSpecReview,
    ) -> SubmittedProjectReviewRef:
        for attempt in range(3):
            try:
                return self._submit_once(command)
            except _RetryStructuredSpecReviewDeadlock:
                if attempt == 2:
                    raise StructuredSpecReviewSubmissionError() from None
        raise StructuredSpecReviewSubmissionError()

    def _submit_once(
        self, command: SubmitStructuredSpecReview,
    ) -> SubmittedProjectReviewRef:
        reviewer_ids = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "structured_solution_spec_id": str(
                    command.structured_solution_spec_id),
                "reviewer_ids": [str(value) for value in reviewer_ids],
                "policy_ref": command.policy_ref,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                self._reviewers.lock_users_in_transaction(
                    tx, reviewer_ids=reviewer_ids)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SOL_SPEC_SUBMIT_REVIEW")
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SOL_SPEC_SUBMIT_REVIEW"
                        or authorized.project_role != "PROJECT_MANAGER"):
                    raise StructuredSpecReviewSubmissionError(
                        "RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    return self._replay(
                        tx, actor, command, reviewer_ids, replay)
                series_id = self._identity.series_for_version(
                    tx, project_id=command.project_id,
                    spec_id=command.structured_solution_spec_id)
                if type(series_id) is not uuid.UUID or series_id.int == 0:
                    raise StructuredSpecReviewSubmissionError(
                        "RESOURCE_NOT_FOUND")
                result = self._reviews.submit_in_transaction(
                    tx, actor_id=actor, project_id=command.project_id,
                    subject_type="SOL-06", subject_id=series_id,
                    subject_version_id=command.structured_solution_spec_id,
                    reviewer_ids=reviewer_ids, policy_code=command.policy_ref,
                    trace_id=command.trace_id,
                    proof_context=ReviewSubjectProofContext(
                        command.session_token, command.trace_id))
                self._validate_result(
                    result, command, reviewer_ids, actor,
                    series_id=series_id)
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(
                        _RESULT_TYPE, result.round_id, 201))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except StructuredSpecReviewSubmissionError:
            raise
        except RuntimeLicenseError:
            raise StructuredSpecReviewSubmissionError(
                "LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise StructuredSpecReviewSubmissionError(exc.code) from None
        except ProjectAuthorizationError as exc:
            code = ("PROJECT_ARCHIVED" if exc.code == "PROJECT_ARCHIVED"
                    else "RESOURCE_NOT_FOUND")
            raise StructuredSpecReviewSubmissionError(code) from None
        except ReviewReviewerEligibilityError:
            raise StructuredSpecReviewSubmissionError(
                "REVIEW_REVIEWER_INELIGIBLE") from None
        except ReviewSubjectAccessDenied:
            raise StructuredSpecReviewSubmissionError(
                "BUSINESS_REVIEW_NOT_ELIGIBLE") from None
        except ReviewSubjectStartError:
            raise StructuredSpecReviewSubmissionError(
                "VALIDATION_FAILED") from None
        except ReviewRoundPersistError as exc:
            code = {
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise StructuredSpecReviewSubmissionError(code) from None
        except Exception as exc:
            if (self._reviews.is_retryable_deadlock(exc)
                    or self._replays.is_retryable_deadlock(exc)):
                raise _RetryStructuredSpecReviewDeadlock() from None
            raise StructuredSpecReviewSubmissionError() from None

    def _replay(
        self, tx: object, actor: uuid.UUID,
        command: SubmitStructuredSpecReview,
        reviewer_ids: tuple[uuid.UUID, ...], receipt: IdempotencyResult,
    ) -> SubmittedProjectReviewRef:
        if (type(receipt) is not IdempotencyResult
                or receipt.ref_type != _RESULT_TYPE
                or receipt.status_code != 201):
            raise StructuredSpecReviewSubmissionError()
        persisted = self._replays.get_project_submission(
            tx, project_id=command.project_id, round_id=receipt.ref_id)
        if type(persisted) is not PersistedProjectReviewSubmission:
            raise StructuredSpecReviewSubmissionError()
        persisted.__post_init__()
        result = persisted.submission
        self._validate_result(
            result, command, reviewer_ids, actor,
            series_id=persisted.review.subject_id)
        if result.round_id != receipt.ref_id:
            raise StructuredSpecReviewSubmissionError()
        self._subjects.require_start_replay_access_in_transaction(
            tx, actor_id=actor, review=persisted.review, round_ref=result)
        return result

    @classmethod
    def _validate(
        cls, command: SubmitStructuredSpecReview,
    ) -> tuple[uuid.UUID, ...]:
        if (type(command) is not SubmitStructuredSpecReview
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (
                           command.trace_id, command.project_id,
                           command.structured_solution_spec_id))
                or type(command.reviewer_ids) is not tuple
                or not 1 <= len(command.reviewer_ids) <= 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in command.reviewer_ids)
                or len(set(command.reviewer_ids)) != len(command.reviewer_ids)
                or command.policy_ref != cls.POLICY_REF):
            raise StructuredSpecReviewSubmissionError("VALIDATION_FAILED")
        return tuple(sorted(command.reviewer_ids, key=str))

    @staticmethod
    def _validate_result(
        result: object, command: SubmitStructuredSpecReview,
        reviewer_ids: tuple[uuid.UUID, ...], actor: uuid.UUID,
        *, series_id: uuid.UUID,
    ) -> None:
        if (type(result) is not SubmittedProjectReviewRef
                or type(series_id) is not uuid.UUID or series_id.int == 0
                or result.project_id != command.project_id
                or result.subject_type != "SOL-06"
                or result.subject_id != series_id
                or result.subject_version_id
                != command.structured_solution_spec_id
                or result.policy_code != command.policy_ref
                or result.reviewer_ids != reviewer_ids
                or result.submitted_by != actor
                or result.round_no != 1
                or result.review_after_version != 1):
            raise StructuredSpecReviewSubmissionError()
        result.__post_init__()

    def _actor(
        self, tx: object, command: SubmitStructuredSpecReview,
    ) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise StructuredSpecReviewSubmissionError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise StructuredSpecReviewSubmissionError("AUTH_ACCESS_DENIED")
        return actor
