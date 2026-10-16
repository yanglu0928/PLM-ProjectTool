"""Build the server-owned AI_TASK Content Plan during Egress Preview."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from plm_assistant.modules.ai.application.create_task import input_refs_fingerprint
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentIdentityQuery,
    AIExecutionContentPlan,
    AIExecutionContentProjection,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionEnvelope,
    AIExecutionEnvelopeBuilder,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptPlanningContent,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionInputRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskSubmissionPolicyRegistry,
    ResolvedAITaskSubmissionPolicy,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class AIEgressTaskPlanError(RuntimeError):
    def __init__(self, code: str = "AI_EGRESS_TASK_PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AITaskPreviewPlanRequest:
    task_type: str
    prompt_policy_ref: str
    output_schema_ref: str
    context_policy_ref: str
    task_parameters: dict[str, object] = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.task_type) is not str or not self.task_type
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.prompt_policy_ref, self.output_schema_ref,
                           self.context_policy_ref,
                       ))
                or type(self.task_parameters) is not dict
                or len(self.task_parameters) > 16):
            raise AIEgressTaskPlanError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AIExecutionPreviewRoute:
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    provider_model_key: str
    model_revision: str
    data_region: str

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                    self.ai_provider_id, self.provider_config_version_id,
                    self.ai_model_id,
                ))
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.provider_model_key, self.model_revision,
                       ))
                or type(self.data_region) is not str
                or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", self.data_region) is None):
            raise AIEgressTaskPlanError()


@dataclass(frozen=True, slots=True)
class AIExecutionPreviewPlanRequest:
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    purpose_ref: str
    minimal_payload_policy_ref: str
    allowed_data_categories: tuple[str, ...]
    inputs: tuple[AIResolvedInputVersionRef, ...]
    route: AIExecutionPreviewRoute
    task: AITaskPreviewPlanRequest

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                    self.project_id, self.requested_by, self.trace_id,
                ))
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.purpose_ref, self.minimal_payload_policy_ref,
                       ))
                or type(self.allowed_data_categories) is not tuple
                or not 1 <= len(self.allowed_data_categories) <= 64
                or tuple(sorted(self.allowed_data_categories))
                   != self.allowed_data_categories
                or len(set(self.allowed_data_categories))
                   != len(self.allowed_data_categories)
                or any(type(value) is not str
                       or _CATEGORY.fullmatch(value) is None
                       for value in self.allowed_data_categories)
                or type(self.inputs) is not tuple or not self.inputs
                or any(type(value) is not AIResolvedInputVersionRef
                       or value.scope != "PROJECT"
                       or value.project_id != self.project_id
                       for value in self.inputs)
                or type(self.route) is not AIExecutionPreviewRoute
                or type(self.task) is not AITaskPreviewPlanRequest):
            raise AIEgressTaskPlanError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class BuiltAIExecutionPreviewPlan:
    plan: AIExecutionContentPlan
    projections: tuple[AIExecutionContentProjection, ...] = field(repr=False)
    prompt_content: AIExecutionPromptPlanningContent = field(repr=False)
    envelope: AIExecutionEnvelope = field(repr=False)


class AIExecutionPreviewPromptOwnerPort(Protocol):
    def resolve_current(
        self, transaction: object, *, policy: ResolvedAITaskSubmissionPolicy,
    ) -> AIExecutionPromptPlanningContent: ...


class AIExecutionPreviewSourceOwnerPort(Protocol):
    selection_policy_ref: str

    def resolve_projection(
        self, transaction: object, query: AIExecutionContentIdentityQuery,
        input_ref: AITaskExecutionInputRef,
    ) -> AIExecutionContentProjection: ...


class AIExecutionPreviewPlanBuilder:
    def __init__(
        self, *, task_policies: AITaskSubmissionPolicyRegistry,
        prompt_owner: AIExecutionPreviewPromptOwnerPort,
        source_owners: Mapping[str, AIExecutionPreviewSourceOwnerPort],
        envelope_builder: AIExecutionEnvelopeBuilder,
    ) -> None:
        if (type(task_policies) is not AITaskSubmissionPolicyRegistry
                or prompt_owner is None or envelope_builder is None
                or not isinstance(source_owners, Mapping) or not source_owners
                or any(type(key) is not str or owner is None
                       for key, owner in source_owners.items())):
            raise ValueError("AI Egress Task Plan dependencies required")
        self._policies = task_policies
        self._prompt = prompt_owner
        self._sources = dict(source_owners)
        self._envelopes = envelope_builder

    def build(
        self, transaction: object, *, request: AIExecutionPreviewPlanRequest,
    ) -> BuiltAIExecutionPreviewPlan:
        if transaction is None or type(request) is not AIExecutionPreviewPlanRequest:
            raise AIEgressTaskPlanError("VALIDATION_FAILED")
        request.__post_init__()
        try:
            policy = self._policies.resolve(
                reference=request.task.prompt_policy_ref,
                task_type=request.task.task_type,
                output_schema_ref=request.task.output_schema_ref,
                context_policy_ref=request.task.context_policy_ref,
                parameters=request.task.task_parameters,
            )
            if policy.purpose_ref != request.purpose_ref:
                raise AIEgressTaskPlanError("AI_EGRESS_TASK_PLAN_POLICY_INVALID")
            prompt = self._prompt.resolve_current(transaction, policy=policy)
            if (type(prompt) is not AIExecutionPromptPlanningContent
                    or prompt.task_type != policy.task_type
                    or prompt.prompt_policy_ref != policy.reference
                    or prompt.prompt_policy_version != policy.policy_version
                    or prompt.prompt_template_id != policy.prompt_template_id
                    or prompt.output_schema_ref != policy.output_schema_ref
                    or prompt.context_policy_ref != policy.context_policy_ref):
                raise AIEgressTaskPlanError()
            content_plan_id = uuid.UUID(new_uuid7())
            input_refs = tuple(AITaskExecutionInputRef(
                ordinal, item.resource_type, item.owner_module,
                item.object_type, item.object_id, item.version_id,
                request.project_id,
            ) for ordinal, item in enumerate(request.inputs, 1))
            projections: list[AIExecutionContentProjection] = []
            for input_ref in input_refs:
                owner = self._sources.get(input_ref.resource_type)
                selection_ref = getattr(owner, "selection_policy_ref", None)
                if owner is None or type(selection_ref) is not str:
                    raise AIEgressTaskPlanError(
                        "AI_EGRESS_TASK_PLAN_SOURCE_UNAVAILABLE")
                query = AIExecutionContentIdentityQuery(
                    content_plan_id, request.project_id, request.requested_by,
                    request.trace_id, request.purpose_ref,
                    request.minimal_payload_policy_ref, selection_ref,
                )
                projection = owner.resolve_projection(
                    transaction, query, input_ref,
                )
                if (type(projection) is not AIExecutionContentProjection
                        or projection.source.ordinal != input_ref.ordinal
                        or projection.source.resource_type != input_ref.resource_type
                        or projection.source.owner_module != input_ref.owner_module
                        or projection.source.object_type != input_ref.object_type
                        or projection.source.object_id != input_ref.object_id
                        or projection.source.version_id != input_ref.version_id
                        or projection.source.project_id != input_ref.project_id):
                    raise AIEgressTaskPlanError(
                        "AI_EGRESS_TASK_PLAN_SOURCE_UNAVAILABLE")
                projection.__post_init__()
                projections.append(projection)
            plan = AIExecutionContentPlan(
                content_plan_id, 1, request.project_id, request.purpose_ref,
                policy.task_type, input_refs_fingerprint(request.inputs),
                tuple(value.source for value in projections),
                AIExecutionPromptIdentity(
                    prompt.prompt_policy_ref, prompt.prompt_policy_version,
                    prompt.prompt_template_id, prompt.prompt_version_no,
                    prompt.system_template_hash, prompt.user_template_hash,
                    prompt.provider_policy_ref, prompt.output_schema_ref,
                    prompt.schema_version, "strict-placeholders.v1", 1,
                ),
                prompt.task_parameters_fingerprint,
                AIExecutionContextIdentity(policy.context_policy_ref, "NONE"),
                request.route.ai_provider_id,
                request.route.provider_config_version_id,
                request.route.ai_model_id, request.route.provider_model_key,
                request.route.model_revision, request.route.data_region,
                request.allowed_data_categories,
                request.minimal_payload_policy_ref,
                "provider-neutral-json.v1", 1,
                "utf8-byte-upper-bound.v1", 1,
            )
            envelope = self._envelopes.build(
                plan=plan, sources=tuple(projections),
                prompt_content=prompt,
            )
            return BuiltAIExecutionPreviewPlan(
                plan, tuple(projections), prompt, envelope,
            )
        except AIEgressTaskPlanError:
            raise
        except Exception:
            raise AIEgressTaskPlanError() from None
