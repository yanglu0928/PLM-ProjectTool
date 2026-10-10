"""Authorized, non-secret options for one project AI Task submission flow."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicy, EgressPreviewPolicyRegistry,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskSubmissionPolicy, AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class AITaskSubmissionOptionsError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_OPTIONS_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GetAITaskSubmissionOptions:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or any(type(value) is not uuid.UUID or not value.int
                       for value in (self.trace_id, self.project_id))):
            raise AITaskSubmissionOptionsError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AITaskRouteCandidate:
    provider_id: uuid.UUID
    model_id: uuid.UUID
    provider_display_name: str
    data_region: str
    provider_kind: ProviderKind
    endpoint_policy_ref: str = field(repr=False)
    egress_class: str = field(repr=False)
    provider_model_key: str
    model_revision: str


@dataclass(frozen=True, slots=True)
class AITaskSubmissionOptionsView:
    task_policies: tuple[AITaskSubmissionPolicy, ...]
    egress_policies: tuple[EgressPreviewPolicy, ...]
    routes: tuple[AITaskRouteCandidate, ...]

    def __post_init__(self) -> None:
        if (not self.task_policies or not self.egress_policies
                or type(self.routes) is not tuple
                or any(type(item) is not AITaskRouteCandidate for item in self.routes)
                or len({(item.provider_id, item.model_id) for item in self.routes})
                   != len(self.routes)):
            raise AITaskSubmissionOptionsError()


class AITaskSubmissionOptionsAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes | None, now: datetime) -> uuid.UUID | None: ...


class AITaskSubmissionOptionsRepositoryPort(Protocol):
    def list_routes(self, transaction: object, *, limit: int) -> tuple[AITaskRouteCandidate, ...]: ...


class AITaskSubmissionOptionsService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: AITaskSubmissionOptionsAccessPort, license_guard: object,
        authorization: ProjectAuthorizationService,
        repository: AITaskSubmissionOptionsRepositoryPort,
        task_policies: AITaskSubmissionPolicyRegistry,
        egress_policies: EgressPreviewPolicyRegistry,
        execution_policies: AIProviderExecutionPolicyRegistry,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository,
            task_policies, egress_policies, execution_policies,
        )):
            raise ValueError("AI Task submission option dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._tasks, self._egress, self._execution = (
            task_policies, egress_policies, execution_policies,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: GetAITaskSubmissionOptions) -> AITaskSubmissionOptionsView:
        if type(query) is not GetAITaskSubmissionOptions:
            raise AITaskSubmissionOptionsError("VALIDATION_FAILED")
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                    raise AITaskSubmissionOptionsError()
                actor = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    csrf_token=None, now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or not actor.int:
                    raise AITaskSubmissionOptionsError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    transaction, user_id=actor, project_id=query.project_id,
                    operation="AI_TASK_OPTIONS_GET",
                )
                candidates = self._repository.list_routes(transaction, limit=201)
                if type(candidates) is not tuple or len(candidates) > 200:
                    raise AITaskSubmissionOptionsError()
                routes = tuple(item for item in candidates if self._execution.permits(
                    reference=item.endpoint_policy_ref,
                    provider_kind=item.provider_kind,
                    data_region=item.data_region, egress_class=item.egress_class,
                    provider_model_key=item.provider_model_key,
                ))
                view = AITaskSubmissionOptionsView(
                    self._tasks.snapshot(),
                    tuple(policy for policy in self._egress.snapshot()
                          if "AI_TASK" in policy.allowed_operation_types),
                    routes,
                )
                self._guard.require_valid(trace_id=query.trace_id)
                return view
        except AITaskSubmissionOptionsError:
            raise
        except ProjectAuthorizationError:
            raise AITaskSubmissionOptionsError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise AITaskSubmissionOptionsError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AITaskSubmissionOptionsError() from None
