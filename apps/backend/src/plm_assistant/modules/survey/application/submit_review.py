"""Idempotent Survey Version submission into the PROJECT Review kernel."""

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
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService, ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission, ProjectReviewPersistenceService,
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectStartError,
)


_OPERATION = "V1_SURVEY_VERSION_SUBMIT_REVIEW"
_RESULT_TYPE = "V1_SURVEY_VERSION_REVIEW_SUBMISSION"


class SurveyReviewSubmissionError(RuntimeError):
    def __init__(self, code: str = "SYSTEM_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class _RetrySurveyReviewDeadlock(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitSurveyVersionReview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    reviewer_ids: tuple[uuid.UUID, ...]
    policy_ref: str
    idempotency_key: str = field(repr=False)


class SurveyReviewSubmissionAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class SurveyReviewSubmissionReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class SurveyReviewSubmissionReplayPort(Protocol):
    def get_project_submission(
        self, transaction: object, *, project_id: uuid.UUID, round_id: uuid.UUID,
    ) -> PersistedProjectReviewSubmission | None: ...
    def is_retryable_deadlock(self, error: Exception) -> bool: ...


class SurveyReviewSubmissionService:
    POLICY_REF = "SURVEY_ALL_V1"

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: SurveyReviewSubmissionAccessPort, license_guard: object,
        authorization: ProjectAuthorizationService,
        reviewers: ProjectReviewerQualificationService,
        receipts: SurveyReviewSubmissionReceiptPort,
        replay_repository: SurveyReviewSubmissionReplayPort,
        reviews: ProjectReviewPersistenceService, subjects: object,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, reviewers,
                receipts, replay_repository, reviews, subjects)):
            raise ValueError("Survey Review submission dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._reviewers = authorization, reviewers
        self._receipts, self._replays = receipts, replay_repository
        self._reviews, self._subjects = reviews, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(self, command: SubmitSurveyVersionReview) -> SubmittedProjectReviewRef:
        for attempt in range(3):
            try:
                return self._submit_once(command)
            except _RetrySurveyReviewDeadlock:
                if attempt == 2:
                    raise SurveyReviewSubmissionError() from None
        raise SurveyReviewSubmissionError()

    def _submit_once(
        self, command: SubmitSurveyVersionReview,
    ) -> SubmittedProjectReviewRef:
        reviewers = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_id": str(command.survey_id),
                "survey_version_id": str(command.survey_version_id),
                "reviewer_ids": [str(value) for value in reviewers],
                "policy_ref": command.policy_ref,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                self._reviewers.lock_users_in_transaction(
                    tx, reviewer_ids=reviewers,
                )
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_VERSION_SUBMIT_REVIEW",
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_VERSION_SUBMIT_REVIEW"
                        or authorized.project_role != "PROJECT_MANAGER"):
                    raise SurveyReviewSubmissionError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    return self._replay(tx, actor, command, reviewers, replay)
                result = self._reviews.submit_in_transaction(
                    tx, actor_id=actor, project_id=command.project_id,
                    subject_type="SRV-02", subject_id=command.survey_id,
                    subject_version_id=command.survey_version_id,
                    reviewer_ids=reviewers, policy_code=command.policy_ref,
                    trace_id=command.trace_id,
                )
                self._validate_result(result, command, reviewers, actor)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _RESULT_TYPE, result.round_id, 201,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except SurveyReviewSubmissionError:
            raise
        except RuntimeLicenseError:
            raise SurveyReviewSubmissionError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise SurveyReviewSubmissionError(exc.code) from None
        except ProjectAuthorizationError as exc:
            code = "PROJECT_ARCHIVED" if exc.code == "PROJECT_ARCHIVED" else "RESOURCE_NOT_FOUND"
            raise SurveyReviewSubmissionError(code) from None
        except ReviewReviewerEligibilityError:
            raise SurveyReviewSubmissionError("REVIEW_REVIEWER_INELIGIBLE") from None
        except ReviewSubjectAccessDenied:
            raise SurveyReviewSubmissionError("BUSINESS_REVIEW_NOT_ELIGIBLE") from None
        except ReviewSubjectStartError:
            raise SurveyReviewSubmissionError("VALIDATION_FAILED") from None
        except ReviewRoundPersistError as exc:
            mapped = {
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise SurveyReviewSubmissionError(mapped) from None
        except Exception as exc:
            if (self._reviews.is_retryable_deadlock(exc)
                    or self._replays.is_retryable_deadlock(exc)):
                raise _RetrySurveyReviewDeadlock() from None
            raise SurveyReviewSubmissionError() from None

    def _replay(
        self, tx: object, actor: uuid.UUID, command: SubmitSurveyVersionReview,
        reviewers: tuple[uuid.UUID, ...], receipt: IdempotencyResult,
    ) -> SubmittedProjectReviewRef:
        if (type(receipt) is not IdempotencyResult
                or receipt.ref_type != _RESULT_TYPE or receipt.status_code != 201):
            raise SurveyReviewSubmissionError()
        persisted = self._replays.get_project_submission(
            tx, project_id=command.project_id, round_id=receipt.ref_id,
        )
        if type(persisted) is not PersistedProjectReviewSubmission:
            raise SurveyReviewSubmissionError()
        persisted.__post_init__()
        result = persisted.submission
        self._validate_result(result, command, reviewers, actor)
        if result.round_id != receipt.ref_id:
            raise SurveyReviewSubmissionError()
        self._subjects.require_start_replay_access_in_transaction(
            tx, actor_id=actor, review=persisted.review, round_ref=result,
        )
        return result

    @classmethod
    def _validate(
        cls, command: SubmitSurveyVersionReview,
    ) -> tuple[uuid.UUID, ...]:
        if (type(command) is not SubmitSurveyVersionReview
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id,
                    command.survey_id, command.survey_version_id,
                ))
                or type(command.reviewer_ids) is not tuple
                or not 1 <= len(command.reviewer_ids) <= 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in command.reviewer_ids)
                or len(set(command.reviewer_ids)) != len(command.reviewer_ids)
                or command.policy_ref != cls.POLICY_REF):
            raise SurveyReviewSubmissionError("VALIDATION_FAILED")
        return tuple(sorted(command.reviewer_ids, key=str))

    @staticmethod
    def _validate_result(
        result: object, command: SubmitSurveyVersionReview,
        reviewers: tuple[uuid.UUID, ...], actor: uuid.UUID,
    ) -> None:
        if (type(result) is not SubmittedProjectReviewRef
                or result.project_id != command.project_id
                or result.subject_type != "SRV-02"
                or result.subject_id != command.survey_id
                or result.subject_version_id != command.survey_version_id
                or result.policy_code != command.policy_ref
                or result.reviewer_ids != reviewers
                or result.submitted_by != actor
                or result.round_no != 1 or result.review_after_version != 1):
            raise SurveyReviewSubmissionError()
        result.__post_init__()

    def _actor(
        self, tx: object, command: SubmitSurveyVersionReview,
    ) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyReviewSubmissionError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyReviewSubmissionError("AUTH_ACCESS_DENIED")
        return actor
