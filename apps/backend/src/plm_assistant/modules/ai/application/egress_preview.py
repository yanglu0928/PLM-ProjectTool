"""Authorized immutable Egress Preview creation and safe detail reads."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Mapping, Protocol

from plm_assistant.modules.ai.application.create_task import input_refs_fingerprint
from plm_assistant.modules.ai.application.egress_task_plan import (
    AIEgressTaskPlanError,
    AIExecutionPreviewPlanBuilder,
    AIExecutionPreviewPlanRequest,
    AIExecutionPreviewRoute,
    AITaskPreviewPlanRequest,
    BuiltAIExecutionPreviewPlan,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
    AIExecutionContentPlanPersistenceError,
    PersistedAIExecutionContentPlan,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResolutionError, AIInputResolutionQuery, AIInputResourceVersionRef,
    AIInputVersionResolver, AIResolvedInputVersionRef,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


_CREATE_OPERATION = "V1_EGRESS_PREVIEW_CREATE"
_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_OPERATIONS = frozenset({"AI_TASK", "RETRIEVAL_RUN", "INDEX_BUILD", "INDEX_REBUILD"})


class EgressPreviewError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateEgressPreview:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    purpose_ref: str
    operation_type: str
    provider_id: uuid.UUID
    model_id: uuid.UUID
    source_refs: tuple[AIInputResourceVersionRef, ...]
    allowed_data_categories: tuple[str, ...]
    minimal_payload_policy_ref: str
    estimated_record_count: int | None
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    payload_fingerprint: bytes | None = field(repr=False)
    ai_task_plan: AITaskPreviewPlanRequest | None = None


@dataclass(frozen=True, slots=True)
class EgressPreviewQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class EgressPreviewSourceView:
    resource_type: str
    resource_id: uuid.UUID
    version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class EgressPreviewView:
    preview_id: uuid.UUID
    project_id: uuid.UUID
    purpose_ref: str
    operation_type: str
    provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    model_id: uuid.UUID
    data_region: str
    allowed_data_categories: tuple[str, ...]
    source_refs: tuple[EgressPreviewSourceView, ...]
    minimal_payload_policy_ref: str
    estimated_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    payload_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    risk_codes: tuple[str, ...]
    created_at: datetime
    expires_at: datetime

    @property
    def preview_fingerprint(self) -> bytes:
        return canonical_payload_fingerprint({
            "preview_id": str(self.preview_id), "project_id": str(self.project_id),
            "purpose_ref": self.purpose_ref, "operation_type": self.operation_type,
            "provider_id": str(self.provider_id),
            "provider_config_version_id": str(self.provider_config_version_id),
            "model_id": str(self.model_id), "data_region": self.data_region,
            "allowed_data_categories": list(self.allowed_data_categories),
            "minimal_payload_policy_ref": self.minimal_payload_policy_ref,
            "estimated_record_count": self.estimated_record_count,
            "max_payload_bytes": self.max_payload_bytes,
            "max_input_tokens": self.max_input_tokens,
            "max_retry_attempts": self.max_retry_attempts,
            "payload_fingerprint": self.payload_fingerprint.hex(),
            "source_refs_fingerprint": self.source_refs_fingerprint.hex(),
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
        })


@dataclass(frozen=True, slots=True)
class EgressRoute:
    provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    model_id: uuid.UUID
    data_region: str
    provider_model_key: str
    model_revision: str


@dataclass(frozen=True, slots=True)
class EgressPreviewPolicy:
    reference: str
    allowed_operation_types: frozenset[str]
    allowed_data_categories: frozenset[str]
    ttl: timedelta
    max_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    risk_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (type(self.reference) is not str or _REF.fullmatch(self.reference) is None
                or type(self.allowed_operation_types) is not frozenset
                or not self.allowed_operation_types
                or not self.allowed_operation_types.issubset(_OPERATIONS)
                or type(self.allowed_data_categories) is not frozenset
                or not 1 <= len(self.allowed_data_categories) <= 64
                or any(type(item) is not str or _CODE.fullmatch(item) is None
                       for item in self.allowed_data_categories)
                or type(self.ttl) is not timedelta
                or not timedelta(minutes=1) <= self.ttl <= timedelta(hours=24)
                or type(self.max_record_count) is not int
                or not 0 <= self.max_record_count <= 1_000_000_000
                or type(self.max_payload_bytes) is not int
                or not 1 <= self.max_payload_bytes <= 1_073_741_824
                or type(self.max_input_tokens) is not int
                or not 1 <= self.max_input_tokens <= 1_048_576
                or type(self.max_retry_attempts) is not int
                or not 1 <= self.max_retry_attempts <= 10
                or type(self.risk_codes) is not tuple
                or not 1 <= len(self.risk_codes) <= 32
                or len(set(self.risk_codes)) != len(self.risk_codes)
                or any(type(item) is not str or _CODE.fullmatch(item) is None
                       for item in self.risk_codes)):
            raise ValueError("invalid Egress Preview policy")


class EgressPreviewPolicyRegistry:
    def __init__(self, policies: Mapping[str, EgressPreviewPolicy]) -> None:
        if (not isinstance(policies, Mapping) or not policies
                or any(type(key) is not str or type(value) is not EgressPreviewPolicy
                       or key != value.reference for key, value in policies.items())):
            raise ValueError("Egress Preview policies required")
        self._policies = MappingProxyType(dict(policies))

    def authorize(self, command: CreateEgressPreview, *, now: datetime) -> tuple[datetime, tuple[str, ...]]:
        policy = self._policies.get(command.minimal_payload_policy_ref)
        if (policy is None or command.operation_type not in policy.allowed_operation_types
                or not set(command.allowed_data_categories).issubset(policy.allowed_data_categories)
                or command.estimated_record_count > policy.max_record_count
                or command.max_payload_bytes > policy.max_payload_bytes
                or command.max_input_tokens > policy.max_input_tokens
                or command.max_retry_attempts > policy.max_retry_attempts):
            raise EgressPreviewError("AI_EGRESS_POLICY_DENIED")
        return now + policy.ttl, policy.risk_codes


@dataclass(frozen=True, slots=True)
class EgressPreviewPersistenceRequest:
    project_id: uuid.UUID
    purpose_ref: str
    operation_type: str
    route: EgressRoute
    allowed_data_categories: tuple[str, ...]
    sources: tuple[AIResolvedInputVersionRef, ...]
    minimal_payload_policy_ref: str
    estimated_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    payload_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    risk_codes: tuple[str, ...]
    created_by: uuid.UUID
    trace_id: uuid.UUID
    expires_at: datetime


class EgressPreviewAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes | None, now: datetime) -> uuid.UUID | None: ...


class EgressPreviewLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class EgressPreviewRepositoryPort(Protocol):
    def resolve_route(self, transaction: object, *, provider_id: uuid.UUID,
                      model_id: uuid.UUID) -> EgressRoute | None: ...
    def create(self, transaction: object, *, request: EgressPreviewPersistenceRequest) -> EgressPreviewView: ...
    def get(self, transaction: object, *, preview_id: uuid.UUID,
            project_id: uuid.UUID) -> EgressPreviewView | None: ...


class EgressPreviewReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class EgressPreviewService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: EgressPreviewAccessPort,
                 license_guard: EgressPreviewLicensePort,
                 authorization: ProjectAuthorizationService,
                 input_resolver: AIInputVersionResolver,
                 policies: EgressPreviewPolicyRegistry,
                 repository: EgressPreviewRepositoryPort,
                 receipts: EgressPreviewReceiptPort, audit: AuditService,
                 task_plan_builder: AIExecutionPreviewPlanBuilder | None = None,
                 content_plan_owner: AIExecutionContentPlanOwner | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, input_resolver,
            policies, repository, receipts, audit,
        )):
            raise ValueError("Egress Preview dependencies required")
        if ((task_plan_builder is None) != (content_plan_owner is None)
                or task_plan_builder is not None
                and type(task_plan_builder) is not AIExecutionPreviewPlanBuilder
                or content_plan_owner is not None
                and type(content_plan_owner) is not AIExecutionContentPlanOwner):
            raise ValueError("AI Egress Task Plan dependencies must be paired")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._inputs, self._policies = authorization, input_resolver, policies
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._task_plans = task_plan_builder
        self._content_plans = content_plan_owner
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateEgressPreview, *, idempotency_key: str) -> EgressPreviewView:
        self._validate_create(command)
        try:
            validate_idempotency_key(idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id), "purpose_ref": command.purpose_ref,
                "operation_type": command.operation_type, "provider_id": str(command.provider_id),
                "model_id": str(command.model_id),
                "source_refs": [{"resource_type": item.resource_type,
                                 "resource_id": str(item.resource_id),
                                 "version_id": str(item.version_id)} for item in command.source_refs],
                "allowed_data_categories": sorted(command.allowed_data_categories),
                "minimal_payload_policy_ref": command.minimal_payload_policy_ref,
                "estimated_record_count": command.estimated_record_count,
                "max_payload_bytes": command.max_payload_bytes,
                "max_input_tokens": command.max_input_tokens,
                "max_retry_attempts": command.max_retry_attempts,
                "payload_fingerprint": (command.payload_fingerprint.hex()
                                        if command.payload_fingerprint else None),
                "ai_task_plan": self._task_plan_fingerprint_fields(
                    command.ai_task_plan),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now, actor = self._actor(tx, command.session_token, command.csrf_token)
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="EGRESS_PREVIEW_CREATE",
                )
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_CREATE_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _CREATE_OPERATION or replay.status_code != 201:
                        raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
                    view = self._repository.get(
                        tx, preview_id=replay.ref_id, project_id=command.project_id,
                    )
                    if type(view) is not EgressPreviewView:
                        raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
                    if command.ai_task_plan is not None:
                        self._require_persisted_plan(tx, view)
                    return view
                sources = self._inputs.resolve_all(
                    tx, AIInputResolutionQuery(command.session_token, command.trace_id),
                    command.project_id, command.source_refs,
                )
                route = self._repository.resolve_route(
                    tx, provider_id=command.provider_id, model_id=command.model_id,
                )
                if type(route) is not EgressRoute:
                    raise EgressPreviewError("AI_EGRESS_ROUTE_UNAVAILABLE")
                planned = self._build_task_plan(
                    tx, command=command, actor=actor, sources=sources,
                    route=route,
                )
                effective = command
                if planned is not None:
                    effective = replace(
                        command,
                        estimated_record_count=planned.envelope.record_count,
                        payload_fingerprint=planned.envelope.payload_fingerprint,
                    )
                    if (planned.envelope.payload_bytes > command.max_payload_bytes
                            or planned.envelope.input_tokens > command.max_input_tokens):
                        raise EgressPreviewError("AI_EGRESS_POLICY_DENIED")
                expires_at, risks = self._policies.authorize(effective, now=now)
                request = EgressPreviewPersistenceRequest(
                    command.project_id, command.purpose_ref, command.operation_type, route,
                    tuple(sorted(command.allowed_data_categories)), sources,
                    command.minimal_payload_policy_ref,
                    effective.estimated_record_count,
                    command.max_payload_bytes, command.max_input_tokens,
                    command.max_retry_attempts, effective.payload_fingerprint,
                    input_refs_fingerprint(sources), risks, actor, command.trace_id, expires_at,
                )
                view = self._repository.create(tx, request=request)
                if type(view) is not EgressPreviewView:
                    raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
                if planned is not None:
                    persisted = self._content_plans.persist(
                        tx, egress_preview_id=view.preview_id,
                        plan=planned.plan, envelope=planned.envelope,
                    )
                    if (type(persisted) is not PersistedAIExecutionContentPlan
                            or persisted.egress_preview_id != view.preview_id
                            or persisted.payload_fingerprint
                               != view.payload_fingerprint
                            or persisted.record_count
                               != view.estimated_record_count):
                        raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_EGRESS_PREVIEW_CREATED", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-04",
                    target_object_id=view.preview_id, after_state="PREVIEWED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_CREATE_OPERATION, view.preview_id, 201),
                )
                tx.commit()
                return view
        except EgressPreviewError:
            raise
        except ProjectAuthorizationError as error:
            raise EgressPreviewError(error.code) from None
        except AIInputResolutionError as error:
            raise EgressPreviewError(error.code) from None
        except IdempotencyError as error:
            raise EgressPreviewError(error.code) from None
        except RuntimeLicenseError:
            raise EgressPreviewError("LICENSE_OPERATION_DENIED") from None
        except (AIEgressTaskPlanError,
                AIExecutionContentPlanPersistenceError):
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE") from None
        except Exception:
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE") from None

    def get(self, query: EgressPreviewQuery, *, preview_id: uuid.UUID) -> EgressPreviewView:
        if (type(query) is not EgressPreviewQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or type(query.project_id) is not uuid.UUID or not query.project_id.int
                or type(preview_id) is not uuid.UUID or not preview_id.int):
            raise EgressPreviewError("VALIDATION_FAILED")
        try:
            with self._uow() as tx:
                _, actor = self._actor(tx, query.session_token, None)
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="EGRESS_PREVIEW_GET",
                )
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                _, actor = self._actor(tx, query.session_token, None)
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="EGRESS_PREVIEW_GET",
                )
                view = self._repository.get(
                    tx, preview_id=preview_id, project_id=query.project_id,
                )
                if type(view) is not EgressPreviewView:
                    raise EgressPreviewError("RESOURCE_NOT_FOUND")
                return view
        except EgressPreviewError:
            raise
        except ProjectAuthorizationError as error:
            raise EgressPreviewError(error.code) from None
        except RuntimeLicenseError:
            raise EgressPreviewError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE") from None

    @staticmethod
    def _validate_create(command: CreateEgressPreview) -> None:
        if (type(command) is not CreateEgressPreview
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or not value.int for value in (
                    command.trace_id, command.project_id, command.provider_id, command.model_id,
                ))
                or type(command.purpose_ref) is not str or _REF.fullmatch(command.purpose_ref) is None
                or command.operation_type not in _OPERATIONS
                or type(command.source_refs) is not tuple or not 1 <= len(command.source_refs) <= 1000
                or type(command.allowed_data_categories) is not tuple
                or not 1 <= len(command.allowed_data_categories) <= 64
                or len(set(command.allowed_data_categories)) != len(command.allowed_data_categories)
                or any(type(item) is not str or _CODE.fullmatch(item) is None
                       for item in command.allowed_data_categories)
                or type(command.minimal_payload_policy_ref) is not str
                or _REF.fullmatch(command.minimal_payload_policy_ref) is None
                or not ((command.ai_task_plan is not None
                         and command.operation_type == "AI_TASK"
                         and command.estimated_record_count is None
                         and command.payload_fingerprint is None)
                        or (command.ai_task_plan is None
                            and type(command.estimated_record_count) is int
                            and 0 <= command.estimated_record_count <= 1_000_000_000
                            and type(command.payload_fingerprint) is bytes
                            and len(command.payload_fingerprint) == 32))
                or type(command.max_payload_bytes) is not int
                or not 1 <= command.max_payload_bytes <= 1_073_741_824
                or type(command.max_input_tokens) is not int
                or not 1 <= command.max_input_tokens <= 1_048_576
                or type(command.max_retry_attempts) is not int
                or not 1 <= command.max_retry_attempts <= 10
                or (command.ai_task_plan is not None
                    and type(command.ai_task_plan) is not AITaskPreviewPlanRequest)):
            raise EgressPreviewError("VALIDATION_FAILED")

    def _build_task_plan(
        self, transaction: object, *, command: CreateEgressPreview,
        actor: uuid.UUID, sources: tuple[AIResolvedInputVersionRef, ...],
        route: EgressRoute,
    ) -> BuiltAIExecutionPreviewPlan | None:
        if command.ai_task_plan is None:
            return None
        if self._task_plans is None or self._content_plans is None:
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
        planned = self._task_plans.build(
            transaction,
            request=AIExecutionPreviewPlanRequest(
                command.project_id, actor, command.trace_id,
                command.purpose_ref, command.minimal_payload_policy_ref,
                tuple(sorted(command.allowed_data_categories)), sources,
                AIExecutionPreviewRoute(
                    route.provider_id, route.provider_config_version_id,
                    route.model_id, route.provider_model_key,
                    route.model_revision, route.data_region,
                ),
                command.ai_task_plan,
            ),
        )
        if type(planned) is not BuiltAIExecutionPreviewPlan:
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
        return planned

    def _require_persisted_plan(
        self, transaction: object, view: EgressPreviewView,
    ) -> PersistedAIExecutionContentPlan:
        if self._content_plans is None:
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
        value = self._content_plans.get_for_preview(
            transaction, egress_preview_id=view.preview_id,
        )
        if (type(value) is not PersistedAIExecutionContentPlan
                or value.egress_preview_id != view.preview_id
                or value.plan.project_id != view.project_id
                or value.plan.purpose_ref != view.purpose_ref
                or value.payload_fingerprint != view.payload_fingerprint
                or value.record_count != view.estimated_record_count):
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
        return value

    @staticmethod
    def _task_plan_fingerprint_fields(
        task: AITaskPreviewPlanRequest | None,
    ) -> dict[str, object] | None:
        if task is None:
            return None
        return {
            "task_type": task.task_type,
            "prompt_policy_ref": task.prompt_policy_ref,
            "output_schema_ref": task.output_schema_ref,
            "context_policy_ref": task.context_policy_ref,
            "task_parameters": task.task_parameters,
        }

    def _actor(self, tx: object, session_token: bytes,
               csrf_token: bytes | None) -> tuple[datetime, uuid.UUID]:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise EgressPreviewError("AI_EGRESS_PREVIEW_UNAVAILABLE")
        now = now.astimezone(timezone.utc)
        actor = self._access.authenticated_user(
            tx, session_token=session_token, csrf_token=csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise EgressPreviewError("AUTH_ACCESS_DENIED")
        return now, actor
