"""Authorized project AI Task metadata read; no prompt text or payload projection."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)


_TASK_STATES = frozenset({
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED",
})
_SUGGESTION_STATES = frozenset({
    "NONE", "AVAILABLE", "ACCEPTED_TO_DRAFT", "REJECTED", "SUPERSEDED",
})
_MANAGEMENT_ROLES = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class AITaskReadError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _time(value: object) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class GetAITask:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    ai_task_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.ai_task_id,
                ))):
            raise AITaskReadError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AITaskInputView:
    resource_type: str
    resource_id: uuid.UUID
    version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AITaskView:
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    task_type: str
    requested_by: uuid.UUID
    input_refs: tuple[AITaskInputView, ...]
    prompt_policy_ref: str
    prompt_policy_version: int | None
    prompt_template_ref: uuid.UUID | None
    prompt_version_no: int | None
    output_schema_ref: str
    context_policy_ref: str
    egress_authorization_ref: uuid.UUID | None
    task_state: str
    suggestion_state: str
    current_invocation_ref: uuid.UUID | None
    job_ref: uuid.UUID | None
    trace_id: uuid.UUID
    error_code: str | None
    retryable: bool | None
    lock_version: int
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    def __post_init__(self) -> None:
        optional_ids = (
            self.prompt_template_ref, self.egress_authorization_ref,
            self.current_invocation_ref, self.job_ref,
        )
        if (not all(_id(value) for value in (
                self.ai_task_id, self.project_id, self.requested_by, self.trace_id,
            ))
                or any(value is not None and not _id(value) for value in optional_ids)
                or type(self.input_refs) is not tuple or not self.input_refs
                or any(type(item) is not AITaskInputView
                       or not _id(item.resource_id) or not _id(item.version_id)
                       for item in self.input_refs)
                or self.task_state not in _TASK_STATES
                or self.suggestion_state not in _SUGGESTION_STATES
                or type(self.lock_version) is not int or self.lock_version < 0
                or not _time(self.requested_at)
                or self.started_at is not None and not _time(self.started_at)
                or self.completed_at is not None and not _time(self.completed_at)
                or ((self.prompt_template_ref is None) != (self.prompt_version_no is None))
                or ((self.prompt_template_ref is None) != (self.prompt_policy_version is None))):
            raise AITaskReadError()


class AITaskReadRepositoryPort(Protocol):
    def get(self, transaction: object, *, ai_task_id: uuid.UUID,
            project_id: uuid.UUID) -> AITaskView | None: ...


class AITaskReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class AITaskReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AITaskReadAccessPort,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: AITaskReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository,
        )):
            raise ValueError("AI Task read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: GetAITask) -> AITaskView:
        if type(query) is not GetAITask:
            raise AITaskReadError("VALIDATION_FAILED")
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if not _time(now):
                    raise AITaskReadError()
                actor = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if not _id(actor):
                    raise AITaskReadError("AUTH_ACCESS_DENIED")
                proof = self._authorization.require_in_transaction(
                    transaction, user_id=actor, project_id=query.project_id,
                    operation="AI_TASK_GET",
                )
                if (type(proof) is not AuthorizedProjectAction
                        or proof.user_id != actor or proof.project_id != query.project_id
                        or proof.operation != "AI_TASK_GET"):
                    raise AITaskReadError("RESOURCE_NOT_FOUND")
                value = self._repository.get(
                    transaction, ai_task_id=query.ai_task_id,
                    project_id=query.project_id,
                )
                if type(value) is not AITaskView:
                    raise AITaskReadError("RESOURCE_NOT_FOUND")
                value.__post_init__()
                if (value.requested_by != actor
                        and proof.project_role not in _MANAGEMENT_ROLES):
                    raise AITaskReadError("RESOURCE_NOT_FOUND")
                self._guard.require_valid(trace_id=query.trace_id)
                return value
        except AITaskReadError:
            raise
        except ProjectAuthorizationError:
            raise AITaskReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise AITaskReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AITaskReadError() from None
