"""Atomic PLAN_VERSION_SUBMIT_REVIEW orchestration; no terminal decision."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)
from plm_assistant.modules.project.application.reviewers import ReviewReviewerEligibilityError
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission, ProjectReviewPersistenceService,
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext, ReviewSubjectStartError,
)


_OPERATION = "V1_PLAN_VERSION_SUBMIT_REVIEW"
_RESULT_TYPE = "V1_PLAN_VERSION_REVIEW_SUBMISSION"


class PlanVersionReviewSubmissionError(RuntimeError):
    def __init__(self, code: str = "SYSTEM_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class _RetryPlanReviewDeadlock(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitPlanVersionReview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID
    reviewer_ids: tuple[uuid.UUID, ...]
    policy_ref: str
    idempotency_key: str = field(repr=False)


class PlanVersionReviewSubmissionService:
    """One ProjectManager command: authenticate, authorize, create and start."""

    POLICY_REF = "PLAN_VERSION_ALL_V1"
    PROJECT_OPERATION = "PLAN_VERSION_SUBMIT_REVIEW"

    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: object, reviewers: object,
                 receipts: object, replay_repository: object,
                 reviews: ProjectReviewPersistenceService, subjects: object,
                 scope_repository: object,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, reviewers,
                receipts, replay_repository, reviews, subjects,
                scope_repository)):
            raise ValueError("PlanVersion Review submission dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._reviewers = authorization, reviewers
        self._receipts, self._replays = receipts, replay_repository
        self._reviews, self._subjects = reviews, subjects
        self._scope = scope_repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(self, command: SubmitPlanVersionReview) -> SubmittedProjectReviewRef:
        for attempt in range(3):
            try:
                return self._submit_once(command)
            except _RetryPlanReviewDeadlock:
                if attempt == 2:
                    raise PlanVersionReviewSubmissionError() from None
        raise PlanVersionReviewSubmissionError()

    def _submit_once(self, command: SubmitPlanVersionReview
                     ) -> SubmittedProjectReviewRef:
        reviewer_ids = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "plan_id": str(command.plan_id),
                "plan_version_id": str(command.plan_version_id),
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
                    operation=self.PROJECT_OPERATION)
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != self.PROJECT_OPERATION
                        or authorized.project_role != "PROJECT_MANAGER"):
                    raise PlanVersionReviewSubmissionError("RESOURCE_NOT_FOUND")
                if self._scope.version_belongs_to_plan(
                        tx, project_id=command.project_id,
                        plan_id=command.plan_id,
                        plan_version_id=command.plan_version_id) is not True:
                    raise PlanVersionReviewSubmissionError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    return self._replay(tx, actor, command, reviewer_ids, replay)
                result = self._reviews.submit_in_transaction(
                    tx, actor_id=actor, project_id=command.project_id,
                    subject_type="PLN-02", subject_id=command.plan_version_id,
                    subject_version_id=command.plan_version_id,
                    reviewer_ids=reviewer_ids, policy_code=command.policy_ref,
                    trace_id=command.trace_id,
                    proof_context=ReviewSubjectProofContext(
                        command.session_token, command.trace_id))
                self._require_result(result, command, reviewer_ids, actor)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _RESULT_TYPE, result.round_id, 201))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except PlanVersionReviewSubmissionError:
            raise
        except RuntimeLicenseError:
            raise PlanVersionReviewSubmissionError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise PlanVersionReviewSubmissionError(exc.code) from None
        except ProjectAuthorizationError as exc:
            code = "PROJECT_ARCHIVED" if exc.code == "PROJECT_ARCHIVED" else "RESOURCE_NOT_FOUND"
            raise PlanVersionReviewSubmissionError(code) from None
        except ReviewReviewerEligibilityError:
            raise PlanVersionReviewSubmissionError("REVIEW_REVIEWER_INELIGIBLE") from None
        except ReviewSubjectAccessDenied:
            raise PlanVersionReviewSubmissionError("BUSINESS_REVIEW_NOT_ELIGIBLE") from None
        except ReviewSubjectStartError:
            raise PlanVersionReviewSubmissionError("VALIDATION_FAILED") from None
        except ReviewRoundPersistError as exc:
            mapped = {
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise PlanVersionReviewSubmissionError(mapped) from None
        except Exception as exc:
            if (self._reviews.is_retryable_deadlock(exc)
                    or self._replays.is_retryable_deadlock(exc)):
                raise _RetryPlanReviewDeadlock() from None
            raise PlanVersionReviewSubmissionError() from None

    def _replay(self, tx, actor, command, reviewer_ids, receipt):
        if (type(receipt) is not IdempotencyResult
                or receipt.ref_type != _RESULT_TYPE or receipt.status_code != 201):
            raise PlanVersionReviewSubmissionError()
        persisted = self._replays.get_project_submission(
            tx, project_id=command.project_id, round_id=receipt.ref_id)
        if type(persisted) is not PersistedProjectReviewSubmission:
            raise PlanVersionReviewSubmissionError()
        persisted.__post_init__()
        result = persisted.submission
        self._require_result(result, command, reviewer_ids, actor)
        if result.round_id != receipt.ref_id:
            raise PlanVersionReviewSubmissionError()
        self._subjects.require_start_replay_access_in_transaction(
            tx, actor_id=actor, review=persisted.review, round_ref=result)
        return result

    @classmethod
    def _validate(cls, command):
        if (type(command) is not SubmitPlanVersionReview
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.plan_id,
                    command.plan_version_id))
                or type(command.reviewer_ids) is not tuple
                or not 1 <= len(command.reviewer_ids) <= 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in command.reviewer_ids)
                or len(set(command.reviewer_ids)) != len(command.reviewer_ids)
                or command.policy_ref != cls.POLICY_REF):
            raise PlanVersionReviewSubmissionError("VALIDATION_FAILED")
        return tuple(sorted(command.reviewer_ids, key=str))

    @staticmethod
    def _require_result(result, command, reviewer_ids, actor):
        if (type(result) is not SubmittedProjectReviewRef
                or result.project_id != command.project_id
                or result.subject_type != "PLN-02"
                or result.subject_id != command.plan_version_id
                or result.subject_version_id != command.plan_version_id
                or result.policy_code != command.policy_ref
                or result.reviewer_ids != reviewer_ids
                or result.submitted_by != actor
                or result.round_no != 1 or result.review_after_version != 1):
            raise PlanVersionReviewSubmissionError()
        result.__post_init__()

    def _actor(self, tx, command):
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PlanVersionReviewSubmissionError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PlanVersionReviewSubmissionError("AUTH_ACCESS_DENIED")
        return actor
