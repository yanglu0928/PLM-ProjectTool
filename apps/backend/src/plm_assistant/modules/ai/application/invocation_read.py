"""Authorized minimal AI Invocation attempt history; no request or response body."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.task_read import (
    AITaskReadRepositoryPort,
    AITaskView,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_STATES = frozenset({"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"})
_SCHEMA_STATES = frozenset({"NOT_APPLICABLE", "PENDING", "VALID", "INVALID"})
_MANAGEMENT_ROLES = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class AIInvocationReadError(RuntimeError):
    def __init__(self, code: str = "AI_INVOCATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _time(value: object) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


def _position(value: object) -> bool:
    return (type(value) is tuple and len(value) == 2
            and type(value[0]) is int and value[0] > 0 and _id(value[1]))


@dataclass(frozen=True, slots=True)
class ListAIInvocations:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    ai_task_id: uuid.UUID
    page_size: int = 50
    before: tuple[int, uuid.UUID] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.ai_task_id))
                or type(self.page_size) is not int or not 1 <= self.page_size <= 100
                or self.before is not None and not _position(self.before)):
            raise AIInvocationReadError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AIInvocationContextView:
    content_plan_id: uuid.UUID
    content_plan_version: int
    context_policy_ref: str
    mode: str
    retrieval_run_id: uuid.UUID | None
    context_bundle_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if (not _id(self.content_plan_id) or self.content_plan_version != 1
                or type(self.context_policy_ref) is not str
                or _REF.fullmatch(self.context_policy_ref) is None
                or self.mode not in {"NONE", "RAG_CONTEXT"}):
            raise AIInvocationReadError()
        if self.mode == "NONE":
            if self.retrieval_run_id is not None or self.context_bundle_id is not None:
                raise AIInvocationReadError()
        elif not _id(self.retrieval_run_id) or not _id(self.context_bundle_id):
            raise AIInvocationReadError()


@dataclass(frozen=True, slots=True)
class AIInvocationView:
    ai_invocation_id: uuid.UUID
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    attempt_no: int
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    model_revision: str
    prompt_template_id: uuid.UUID
    prompt_version_no: int
    output_schema_ref: str
    schema_version: int
    context: AIInvocationContextView | None
    invocation_state: str
    schema_validation_state: str
    usage_input_tokens: int | None
    usage_output_tokens: int | None
    latency_ms: int | None
    error_code: str | None
    retryable: bool | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.ai_invocation_id, self.ai_task_id, self.project_id,
                self.ai_provider_id, self.provider_config_version_id,
                self.ai_model_id, self.prompt_template_id))
                or type(self.attempt_no) is not int or self.attempt_no < 1
                or type(self.model_revision) is not str
                or _MODEL.fullmatch(self.model_revision) is None
                or type(self.prompt_version_no) is not int
                or self.prompt_version_no < 1
                or type(self.output_schema_ref) is not str
                or _REF.fullmatch(self.output_schema_ref) is None
                or type(self.schema_version) is not int or self.schema_version < 1
                or self.context is not None
                and type(self.context) is not AIInvocationContextView
                or self.invocation_state not in _STATES
                or self.schema_validation_state not in _SCHEMA_STATES
                or any(value is not None and (
                    type(value) is not int or value < 0)
                    for value in (
                        self.usage_input_tokens, self.usage_output_tokens,
                        self.latency_ms))
                or self.error_code is not None and (
                    type(self.error_code) is not str
                    or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None)
                or self.retryable is not None and type(self.retryable) is not bool
                or not _time(self.created_at)
                or self.started_at is not None and not _time(self.started_at)
                or self.completed_at is not None and not _time(self.completed_at)):
            raise AIInvocationReadError()
        terminal = self.invocation_state in {"SUCCEEDED", "FAILED", "CANCELLED"}
        if ((terminal and (self.started_at is None or self.completed_at is None))
                or (not terminal and self.completed_at is not None)
                or self.started_at is not None and self.started_at < self.created_at
                or self.completed_at is not None and (
                    self.started_at is None or self.completed_at < self.started_at)
                or self.invocation_state == "FAILED" and (
                    self.error_code is None or self.retryable is None)):
            raise AIInvocationReadError()
        if self.context is not None:
            self.context.__post_init__()


@dataclass(frozen=True, slots=True)
class AIInvocationCandidates:
    items: tuple[AIInvocationView, ...]
    has_more: bool

    def __post_init__(self) -> None:
        if (type(self.items) is not tuple or len(self.items) > 100
                or type(self.has_more) is not bool
                or self.has_more and not self.items):
            raise AIInvocationReadError()
        positions: list[tuple[int, uuid.UUID]] = []
        for item in self.items:
            if type(item) is not AIInvocationView:
                raise AIInvocationReadError()
            item.__post_init__()
            positions.append((item.attempt_no, item.ai_invocation_id))
        if (len({item.ai_invocation_id for item in self.items}) != len(self.items)
                or any(left <= right for left, right in zip(
                    positions, positions[1:], strict=False))):
            raise AIInvocationReadError()


@dataclass(frozen=True, slots=True)
class AIInvocationPage:
    items: tuple[AIInvocationView, ...]
    next_position: tuple[int, uuid.UUID] | None = field(repr=False)
    has_more: bool

    def __post_init__(self) -> None:
        if (type(self.items) is not tuple or len(self.items) > 100
                or type(self.has_more) is not bool
                or self.has_more != (self.next_position is not None)
                or self.next_position is not None and not _position(self.next_position)):
            raise AIInvocationReadError()
        AIInvocationCandidates(self.items, self.has_more).__post_init__()


class AIInvocationRepositoryPort(Protocol):
    def list_page(
        self, transaction: object, *, project_id: uuid.UUID,
        ai_task_id: uuid.UUID, before: tuple[int, uuid.UUID] | None,
        limit: int,
    ) -> AIInvocationCandidates: ...


class AIInvocationListService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 tasks: AITaskReadRepositoryPort,
                 invocations: AIInvocationRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, tasks, invocations,
        )):
            raise ValueError("AI Invocation list dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._tasks = authorization, tasks
        self._invocations = invocations
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list(self, query: ListAIInvocations) -> AIInvocationPage:
        if type(query) is not ListAIInvocations:
            raise AIInvocationReadError("VALIDATION_FAILED")
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if not _time(now):
                    raise AIInvocationReadError()
                actor = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if not _id(actor):
                    raise AIInvocationReadError("AUTH_ACCESS_DENIED")
                proof = self._authorization.require_in_transaction(
                    transaction, user_id=actor, project_id=query.project_id,
                    operation="AI_TASK_INVOCATION_LIST",
                )
                if (type(proof) is not AuthorizedProjectAction
                        or proof.user_id != actor
                        or proof.project_id != query.project_id
                        or proof.operation != "AI_TASK_INVOCATION_LIST"
                        or proof.project_role not in {
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                            "CUSTOMER_MANAGER",
                        }):
                    raise AIInvocationReadError("RESOURCE_NOT_FOUND")
                task = self._tasks.get(
                    transaction, ai_task_id=query.ai_task_id,
                    project_id=query.project_id,
                )
                if (type(task) is not AITaskView
                        or task.requested_by != actor
                        and proof.project_role not in _MANAGEMENT_ROLES):
                    raise AIInvocationReadError("RESOURCE_NOT_FOUND")
                task.__post_init__()
                candidates = self._invocations.list_page(
                    transaction, project_id=query.project_id,
                    ai_task_id=query.ai_task_id, before=query.before,
                    limit=query.page_size,
                )
                if type(candidates) is not AIInvocationCandidates:
                    raise AIInvocationReadError()
                candidates.__post_init__()
                if len(candidates.items) > query.page_size:
                    raise AIInvocationReadError()
                for item in candidates.items:
                    if (item.project_id != query.project_id
                            or item.ai_task_id != query.ai_task_id
                            or query.before is not None and (
                                item.attempt_no, item.ai_invocation_id) >= query.before):
                        raise AIInvocationReadError()
                self._guard.require_valid(trace_id=query.trace_id)
                position = ((candidates.items[-1].attempt_no,
                             candidates.items[-1].ai_invocation_id)
                            if candidates.has_more else None)
                return AIInvocationPage(
                    candidates.items, position, candidates.has_more,
                )
        except AIInvocationReadError:
            raise
        except ProjectAuthorizationError:
            raise AIInvocationReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise AIInvocationReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AIInvocationReadError() from None
