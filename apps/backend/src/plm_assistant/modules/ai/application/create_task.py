"""Authorized atomic AI Task creation; no Provider call is performed here."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResolutionError, AIInputResolutionQuery, AIInputResourceVersionRef,
    AIInputVersionResolver, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskPromptOwner, AITaskPromptOwnerError, AITaskPromptSnapshot,
    AITaskSubmissionPolicyError, AITaskSubmissionPolicyRegistry,
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


_OPERATION = "V1_AI_TASK_CREATE"
_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_TASK_TYPES = frozenset({
    "DOCUMENT_PARSE", "CAPABILITY_EXTRACT", "GAP_ANALYSIS", "SURVEY_GENERATE",
    "SURVEY_ANALYZE", "REQUIREMENT_NORMALIZE", "REQUIREMENT_MATCH",
    "SOLUTION_SUGGEST", "PROTOTYPE_GENERATE", "SOLUTION_GENERATE",
    "PLAN_GENERATE", "OUTPUT_SUMMARIZE",
})
_APPROVER_ROLES = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class AITaskCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EgressAuthorizationOwnerError(RuntimeError):
    def __init__(self, code: str = "AI_EGRESS_AUTHORIZATION_INVALID") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateAITask:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    task_type: str
    input_refs: tuple[AIInputResourceVersionRef, ...]
    prompt_policy_ref: str
    output_schema_ref: str
    context_policy_ref: str
    task_parameters: dict[str, object] = field(repr=False)
    egress_authorization_ref: uuid.UUID


@dataclass(frozen=True, slots=True)
class AuthorizedEgressSnapshot:
    authorization_ref: uuid.UUID
    project_id: uuid.UUID
    purpose_ref: str
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    data_region: str
    allowed_data_categories: tuple[str, ...]
    authorization_fingerprint: bytes = field(repr=False)
    preview_payload_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    approved_by: uuid.UUID
    approved_role: str
    approved_at: datetime
    valid_until: datetime
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    authorization_state: str


@dataclass(frozen=True, slots=True)
class EgressAuthorizationQuery:
    authorization_ref: uuid.UUID
    project_id: uuid.UUID
    task_type: str
    source_refs_fingerprint: bytes = field(repr=False)
    now: datetime


@dataclass(frozen=True, slots=True)
class AITaskPersistenceRequest:
    project_id: uuid.UUID
    task_type: str
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    input_fingerprint: bytes = field(repr=False)
    prompt: AITaskPromptSnapshot
    inputs: tuple[AIResolvedInputVersionRef, ...]
    egress: AuthorizedEgressSnapshot


@dataclass(frozen=True, slots=True)
class CreatedAITask:
    ai_task_id: uuid.UUID
    job_id: uuid.UUID


class AITaskCreateAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class EgressAuthorizationOwnerPort(Protocol):
    def resolve_authorized(self, transaction: object, *,
                           query: EgressAuthorizationQuery) -> AuthorizedEgressSnapshot: ...


class AITaskCreateRepositoryPort(Protocol):
    def create(self, transaction: object, *, request: AITaskPersistenceRequest) -> CreatedAITask: ...
    def replay(self, transaction: object, *, ai_task_id: uuid.UUID,
               project_id: uuid.UUID, requested_by: uuid.UUID) -> CreatedAITask | None: ...


class AITaskCreateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


def input_refs_fingerprint(refs: tuple[AIResolvedInputVersionRef, ...]) -> bytes:
    return canonical_payload_fingerprint([{
        "resource_type": item.resource_type, "owner_module": item.owner_module,
        "object_type": item.object_type, "object_id": str(item.object_id),
        "version_id": str(item.version_id), "scope": item.scope,
        "project_id": str(item.project_id),
    } for item in refs])


class AITaskCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AITaskCreateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 input_resolver: AIInputVersionResolver, egress_owner: EgressAuthorizationOwnerPort,
                 task_policies: AITaskSubmissionPolicyRegistry,
                 prompt_owner: AITaskPromptOwner,
                 repository: AITaskCreateRepositoryPort, receipts: AITaskCreateReceiptPort,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard, authorization,
                                           input_resolver, egress_owner, task_policies,
                                           prompt_owner, repository, receipts, audit)):
            raise ValueError("AI Task create dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._inputs, self._egress = authorization, input_resolver, egress_owner
        self._task_policies, self._prompt_owner = task_policies, prompt_owner
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateAITask, *, idempotency_key: str) -> CreatedAITask:
        self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id), "task_type": command.task_type,
                "input_refs": [{"resource_type": item.resource_type,
                                "resource_id": str(item.resource_id),
                                "version_id": str(item.version_id)} for item in command.input_refs],
                "prompt_policy_ref": command.prompt_policy_ref,
                "output_schema_ref": command.output_schema_ref,
                "context_policy_ref": command.context_policy_ref,
                "task_parameters": command.task_parameters,
                "egress_authorization_ref": str(command.egress_authorization_ref),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor, now = self._actor(tx, command)
                self._require_project(tx, actor, command.project_id)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 202:
                        raise AITaskCreateError("AI_TASK_UNAVAILABLE")
                    result = self._repository.replay(
                        tx, ai_task_id=replay.ref_id, project_id=command.project_id,
                        requested_by=actor,
                    )
                    if type(result) is not CreatedAITask:
                        raise AITaskCreateError("AI_TASK_UNAVAILABLE")
                    return result
                policy = self._task_policies.resolve(
                    reference=command.prompt_policy_ref, task_type=command.task_type,
                    output_schema_ref=command.output_schema_ref,
                    context_policy_ref=command.context_policy_ref,
                    parameters=command.task_parameters,
                )
                prompt = self._prompt_owner.resolve_current(tx, policy=policy)
                inputs = self._inputs.resolve_all(
                    tx, AIInputResolutionQuery(command.session_token, command.trace_id),
                    command.project_id, command.input_refs,
                )
                source_fingerprint = input_refs_fingerprint(inputs)
                egress = self._egress.resolve_authorized(
                    tx, query=EgressAuthorizationQuery(
                        command.egress_authorization_ref, command.project_id,
                        command.task_type, source_fingerprint, now,
                    ),
                )
                self._validate_egress(command, egress, source_fingerprint, now)
                if prompt.purpose_ref != egress.purpose_ref:
                    raise AITaskCreateError("AI_TASK_POLICY_INVALID")
                request = AITaskPersistenceRequest(
                    command.project_id, command.task_type, actor, command.trace_id,
                    source_fingerprint, prompt, inputs, egress,
                )
                result = self._repository.create(tx, request=request)
                if type(result) is not CreatedAITask:
                    raise AITaskCreateError("AI_TASK_UNAVAILABLE")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_TASK_CREATED", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-04",
                    target_object_id=result.ai_task_id, after_state="QUEUED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, result.ai_task_id, 202),
                )
                tx.commit()
                return result
        except AITaskCreateError:
            raise
        except ProjectAuthorizationError as exc:
            raise AITaskCreateError(exc.code) from None
        except AIInputResolutionError as exc:
            raise AITaskCreateError(exc.code) from None
        except EgressAuthorizationOwnerError as exc:
            raise AITaskCreateError(exc.code) from None
        except AITaskSubmissionPolicyError as exc:
            raise AITaskCreateError(exc.code) from None
        except AITaskPromptOwnerError as exc:
            raise AITaskCreateError(exc.code) from None
        except IdempotencyError as exc:
            raise AITaskCreateError(exc.code) from None
        except RuntimeLicenseError:
            raise AITaskCreateError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AITaskCreateError("AI_TASK_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: CreateAITask) -> None:
        if (type(command) is not CreateAITask
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or not command.trace_id.int
                or type(command.project_id) is not uuid.UUID or not command.project_id.int
                or command.task_type not in _TASK_TYPES
                or type(command.input_refs) is not tuple or not 1 <= len(command.input_refs) <= 1000
                or any(type(value) is not str or _REF.fullmatch(value) is None for value in (
                    command.prompt_policy_ref, command.output_schema_ref,
                    command.context_policy_ref,
                ))
                or type(command.task_parameters) is not dict
                or len(command.task_parameters) > 16
                or any(type(key) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key)
                       or type(value) not in (str, int, bool)
                       for key, value in command.task_parameters.items())
                or type(command.egress_authorization_ref) is not uuid.UUID
                or not command.egress_authorization_ref.int):
            raise AITaskCreateError("VALIDATION_FAILED")

    def _actor(self, tx: object, command: CreateAITask) -> tuple[uuid.UUID, datetime]:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AITaskCreateError("AI_TASK_UNAVAILABLE")
        now = now.astimezone(timezone.utc)
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise AITaskCreateError("AUTH_ACCESS_DENIED")
        return actor, now

    def _require_project(self, tx: object, actor: uuid.UUID, project_id: uuid.UUID) -> None:
        self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id, operation="AI_TASK_CREATE",
        )

    @staticmethod
    def _validate_egress(command: CreateAITask, snapshot: AuthorizedEgressSnapshot,
                         source_fingerprint: bytes, now: datetime) -> None:
        if (type(snapshot) is not AuthorizedEgressSnapshot
                or snapshot.authorization_ref != command.egress_authorization_ref
                or snapshot.project_id != command.project_id
                or snapshot.source_refs_fingerprint != source_fingerprint
                or snapshot.authorization_state != "AUTHORIZED"
                or snapshot.approved_role not in _APPROVER_ROLES
                or not all(type(value) is uuid.UUID and value.int for value in (
                    snapshot.ai_provider_id, snapshot.provider_config_version_id,
                    snapshot.ai_model_id, snapshot.approved_by,
                ))
                or any(type(value) is not bytes or len(value) != 32 for value in (
                    snapshot.authorization_fingerprint, snapshot.preview_payload_fingerprint,
                    snapshot.source_refs_fingerprint,
                ))
                or type(snapshot.allowed_data_categories) is not tuple
                or not 1 <= len(snapshot.allowed_data_categories) <= 64
                or len(set(snapshot.allowed_data_categories)) != len(snapshot.allowed_data_categories)
                or any(type(item) is not str or not 1 <= len(item) <= 64
                       or item != item.strip() for item in snapshot.allowed_data_categories)
                or type(snapshot.purpose_ref) is not str or _REF.fullmatch(snapshot.purpose_ref) is None
                or type(snapshot.data_region) is not str
                or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", snapshot.data_region)
                or not isinstance(snapshot.approved_at, datetime)
                or snapshot.approved_at.tzinfo is None
                or not isinstance(snapshot.valid_until, datetime)
                or snapshot.valid_until.tzinfo is None
                or snapshot.approved_at.astimezone(timezone.utc) > now
                or now >= snapshot.valid_until.astimezone(timezone.utc)
                or type(snapshot.max_payload_bytes) is not int
                or not 1 <= snapshot.max_payload_bytes <= 1_073_741_824
                or type(snapshot.max_input_tokens) is not int
                or not 1 <= snapshot.max_input_tokens <= 1_048_576
                or type(snapshot.max_retry_attempts) is not int
                or not 1 <= snapshot.max_retry_attempts <= 10):
            raise AITaskCreateError("AI_EGRESS_AUTHORIZATION_INVALID")
