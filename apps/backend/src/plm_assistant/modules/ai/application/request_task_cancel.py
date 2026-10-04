"""Current-authorized, idempotent AI Task Job cancellation Owner."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import DBAPIError

from plm_assistant.modules.jobs.application.cancel_request import (
    JobCancelError,
    JobCancelResult,
    RequestProjectJobCancel,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
)

from .cancel_task_execution import (
    AITaskCancellationError,
    AITaskCancellationOwner,
    CancelAITaskExecution,
    CancelledAITaskExecution,
)


@dataclass(frozen=True, slots=True)
class AITaskCancellationBinding:
    ai_task_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    task_lock_version: int
    job_lock_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.ai_task_id, self.job_id, self.project_id,
                self.requested_by))
                or any(type(value) is not int or value < 0 for value in (
                    self.task_lock_version, self.job_lock_version))):
            raise AITaskCancellationError()


class AITaskJobCancelOwner:
    """Adapter for the frozen Project Job cancel endpoint."""

    def __init__(
        self, *, unit_of_work, store, session_access, projects,
        license_guard, receipts, audit,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, store, session_access, projects, license_guard,
                receipts, audit)):
            raise ValueError("Current AI cancellation dependencies required")
        self._uow = unit_of_work
        self._store = store
        self._access = session_access
        self._projects = projects
        self._guard = license_guard
        self._receipts = receipts
        self._core = AITaskCancellationOwner(
            unit_of_work=unit_of_work, store=store, audit=audit,
        )

    @staticmethod
    def _deadlock(error: BaseException) -> bool:
        seen: set[int] = set()
        for _ in range(16):
            if id(error) in seen:
                return False
            seen.add(id(error))
            if (isinstance(error, DBAPIError)
                    and getattr(error.orig, "sqlstate", None) == "40P01"):
                return True
            nested = error.__cause__ or error.__context__
            if not isinstance(nested, BaseException):
                return False
            error = nested
        return False

    def _authorize(
        self, transaction, command: RequestProjectJobCancel,
        binding: AITaskCancellationBinding,
    ) -> uuid.UUID:
        self._guard.require_valid(trace_id=command.trace_id)
        actor = self._access.authenticated_user(
            transaction, session_token=command.session_token,
            csrf_token=command.csrf_token, now=datetime.now(timezone.utc),
        )
        if actor is None:
            raise JobCancelError("RESOURCE_NOT_FOUND")
        proof = self._projects.require_in_transaction(
            transaction, user_id=actor, project_id=command.project_id,
            operation="JOB_PROJECT_CANCEL",
        )
        if (proof.user_id != actor or proof.project_id != command.project_id
                or (actor != binding.requested_by
                    and proof.project_role != "PROJECT_MANAGER")):
            raise JobCancelError("RESOURCE_NOT_FOUND")
        return actor

    def cancel(
        self, command: RequestProjectJobCancel, *, idempotency_key: str,
    ) -> JobCancelResult:
        if type(command) is not RequestProjectJobCancel:
            raise JobCancelError("VALIDATION_FAILED")
        command.__post_init__()
        try:
            validate_idempotency_key(idempotency_key)
        except IdempotencyError as exc:
            raise JobCancelError(exc.code) from None
        for attempt in range(3):
            try:
                return self._cancel_once(command, idempotency_key)
            except Exception as exc:
                if self._deadlock(exc):
                    if attempt < 2:
                        continue
                    raise JobCancelError() from None
                if isinstance(exc, JobCancelError):
                    raise
                if isinstance(exc, IdempotencyError):
                    raise JobCancelError(exc.code) from None
                if isinstance(exc, ProjectAuthorizationError):
                    raise JobCancelError("RESOURCE_NOT_FOUND") from None
                if isinstance(exc, RuntimeLicenseError):
                    raise JobCancelError("LICENSE_OPERATION_DENIED") from None
                if isinstance(exc, AITaskCancellationError):
                    code = {
                        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                        "CONFLICT_VERSION": "CONFLICT_VERSION",
                        "VALIDATION_FAILED": "VALIDATION_FAILED",
                    }.get(exc.code, "JOB_UNAVAILABLE")
                    raise JobCancelError(code) from None
                raise JobCancelError() from None
        raise JobCancelError()

    def _cancel_once(
        self, command: RequestProjectJobCancel, key: str,
    ) -> JobCancelResult:
        with self._uow() as transaction:
            binding = self._store.binding(
                transaction, job_id=command.job_id,
                project_id=command.project_id,
            )
            if type(binding) is not AITaskCancellationBinding:
                raise JobCancelError("RESOURCE_NOT_FOUND")
            binding.__post_init__()
            actor = self._authorize(transaction, command, binding)
            scope = IdempotencyScope.from_key(
                actor_id=actor, project_id=command.project_id,
                operation="V1_AI_TASK_CANCEL", key=key,
            )
            fingerprint = canonical_payload_fingerprint({
                "ai_task_id": str(binding.ai_task_id),
                "job_id": str(command.job_id),
                "reason": command.reason,
                "expected_version": command.expected_version,
            })
            replay = self._receipts.reserve(
                transaction, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if (type(replay) is not IdempotencyResult
                        or replay.ref_type != "V1_AI_TASK_CANCEL"
                        or replay.status_code != 200):
                    raise JobCancelError()
                result = self._store.receipt(
                    transaction, binding=binding, actor_id=actor,
                    audit_event_id=replay.ref_id,
                )
            else:
                if binding.job_lock_version != command.expected_version:
                    raise JobCancelError("CONFLICT_VERSION")
                result, event_id = self._core.cancel_in_transaction(
                    transaction, CancelAITaskExecution(
                        binding.ai_task_id, binding.project_id, actor,
                        command.trace_id, binding.task_lock_version,
                        command.reason,
                    ),
                )
                self._receipts.complete(
                    transaction, scope=scope,
                    result=IdempotencyResult(
                        "V1_AI_TASK_CANCEL", event_id, 200,
                    ),
                )
            if (type(result) is not CancelledAITaskExecution
                    or result.ai_task_id != binding.ai_task_id
                    or result.job_id != binding.job_id
                    or result.project_id != binding.project_id):
                raise JobCancelError()
            result.__post_init__()
            if self._authorize(transaction, command, binding) != actor:
                raise JobCancelError("RESOURCE_NOT_FOUND")
            response = JobCancelResult(
                result.job_id, result.state,
                result.changed and result.state not in {"SUCCEEDED", "FAILED"},
                result.job_lock_version,
            )
            if replay is None:
                transaction.commit()
            return response
