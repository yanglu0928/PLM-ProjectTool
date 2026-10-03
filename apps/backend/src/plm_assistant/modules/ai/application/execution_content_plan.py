"""Immutable, no-content identity plan for deterministic AI execution.

The plan deliberately carries only identities, digests, sizes and policy
versions. Prompt text, input text, task parameter values and provider secrets
belong to short-lived Owner projections implemented by later slices.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)


_PUBLIC_TYPE = re.compile(r"^[A-Z][A-Z0-9-]{0,63}$")
_OWNER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OBJECT = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_KIND = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_CONTEXT_MODES = frozenset({"NONE", "RAG_CONTEXT"})


class AIExecutionContentPlanError(RuntimeError):
    def __init__(self, code: str = "AI_EXECUTION_CONTENT_PLAN_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


@dataclass(frozen=True, slots=True)
class AIExecutionContentSourceIdentity:
    """Exact Owner projection identity; never carries content or a locator."""

    ordinal: int
    resource_type: str
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    project_id: uuid.UUID
    content_kind: str
    content_revision_id: uuid.UUID
    content_object_id: uuid.UUID
    producer_ref: str
    producer_version: str
    content_schema_ref: str
    selection_policy_ref: str
    source_fingerprint: bytes = field(repr=False)
    content_fingerprint: bytes = field(repr=False)
    projection_fingerprint: bytes = field(repr=False)
    content_size_bytes: int
    record_count: int

    def __post_init__(self) -> None:
        if (type(self.ordinal) is not int or not 1 <= self.ordinal <= 1000
                or type(self.resource_type) is not str
                or _PUBLIC_TYPE.fullmatch(self.resource_type) is None
                or type(self.owner_module) is not str
                or _OWNER.fullmatch(self.owner_module) is None
                or type(self.object_type) is not str
                or _OBJECT.fullmatch(self.object_type) is None
                or not all(_id(value) for value in (
                    self.object_id, self.version_id, self.project_id,
                    self.content_revision_id, self.content_object_id,
                ))
                or type(self.content_kind) is not str
                or _KIND.fullmatch(self.content_kind) is None
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.producer_ref, self.content_schema_ref,
                           self.selection_policy_ref,
                       ))
                or type(self.producer_version) is not str
                or _MODEL.fullmatch(self.producer_version) is None
                or not _digest(self.source_fingerprint)
                or not _digest(self.content_fingerprint)
                or not _digest(self.projection_fingerprint)
                or type(self.content_size_bytes) is not int
                or not 1 <= self.content_size_bytes <= 1_073_741_824
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 1_000_000_000):
            raise AIExecutionContentPlanError()


@dataclass(frozen=True, slots=True)
class AIExecutionPromptIdentity:
    prompt_policy_ref: str
    prompt_policy_version: int
    prompt_template_id: uuid.UUID
    prompt_version_no: int
    system_template_hash: str
    user_template_hash: str
    provider_policy_ref: str
    output_schema_ref: str
    schema_version: int
    rendering_policy_ref: str
    rendering_policy_version: int

    def __post_init__(self) -> None:
        refs = (
            self.prompt_policy_ref, self.provider_policy_ref,
            self.output_schema_ref, self.rendering_policy_ref,
        )
        hashes = (self.system_template_hash, self.user_template_hash)
        if (not _id(self.prompt_template_id)
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in refs)
                or any(type(value) is not str
                       or re.fullmatch(r"[0-9a-f]{64}", value) is None
                       for value in hashes)
                or any(type(value) is not int or not 1 <= value <= 2_147_483_647
                       for value in (
                           self.prompt_policy_version, self.prompt_version_no,
                           self.schema_version, self.rendering_policy_version,
                       ))):
            raise AIExecutionContentPlanError()


@dataclass(frozen=True, slots=True)
class AIExecutionContextIdentity:
    context_policy_ref: str
    mode: str
    retrieval_run_id: uuid.UUID | None = None
    context_bundle_id: uuid.UUID | None = None
    context_bundle_fingerprint: bytes | None = field(default=None, repr=False)
    record_count: int = 0
    content_size_bytes: int = 0

    def __post_init__(self) -> None:
        if (type(self.context_policy_ref) is not str
                or _REF.fullmatch(self.context_policy_ref) is None
                or self.mode not in _CONTEXT_MODES
                or type(self.record_count) is not int
                or not 0 <= self.record_count <= 1_000_000_000
                or type(self.content_size_bytes) is not int
                or not 0 <= self.content_size_bytes <= 1_073_741_824):
            raise AIExecutionContentPlanError()
        if self.mode == "NONE":
            if (self.retrieval_run_id is not None
                    or self.context_bundle_id is not None
                    or self.context_bundle_fingerprint is not None
                    or self.record_count != 0 or self.content_size_bytes != 0):
                raise AIExecutionContentPlanError()
            return
        if (not _id(self.retrieval_run_id)
                or not _id(self.context_bundle_id)
                or not _digest(self.context_bundle_fingerprint)
                or self.record_count < 1 or self.content_size_bytes < 1):
            raise AIExecutionContentPlanError()


@dataclass(frozen=True, slots=True)
class AIExecutionContentPlan:
    """Persistable identity graph used by Preview, Task and Invocation."""

    content_plan_id: uuid.UUID
    content_plan_version: int
    project_id: uuid.UUID
    purpose_ref: str
    task_type: str
    source_refs_fingerprint: bytes = field(repr=False)
    sources: tuple[AIExecutionContentSourceIdentity, ...]
    prompt: AIExecutionPromptIdentity
    task_parameters_fingerprint: bytes = field(repr=False)
    context: AIExecutionContextIdentity
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    provider_model_key: str
    model_revision: str
    data_region: str
    allowed_data_categories: tuple[str, ...]
    minimal_payload_policy_ref: str
    envelope_encoding_ref: str
    envelope_encoding_version: int
    token_estimator_ref: str
    token_estimator_version: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.content_plan_id, self.project_id, self.ai_provider_id,
                    self.provider_config_version_id, self.ai_model_id,
                ))
                or type(self.content_plan_version) is not int
                or self.content_plan_version != 1
                or type(self.purpose_ref) is not str
                or _REF.fullmatch(self.purpose_ref) is None
                or type(self.task_type) is not str or not self.task_type
                or not _digest(self.source_refs_fingerprint)
                or type(self.sources) is not tuple or not self.sources
                or any(type(source) is not AIExecutionContentSourceIdentity
                       or source.ordinal != ordinal
                       or source.project_id != self.project_id
                       for ordinal, source in enumerate(self.sources, 1))
                or type(self.prompt) is not AIExecutionPromptIdentity
                or not _digest(self.task_parameters_fingerprint)
                or type(self.context) is not AIExecutionContextIdentity
                or type(self.provider_model_key) is not str
                or _MODEL.fullmatch(self.provider_model_key) is None
                or type(self.model_revision) is not str
                or _MODEL.fullmatch(self.model_revision) is None
                or type(self.data_region) is not str
                or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", self.data_region) is None
                or type(self.allowed_data_categories) is not tuple
                or not 1 <= len(self.allowed_data_categories) <= 64
                or tuple(sorted(self.allowed_data_categories))
                   != self.allowed_data_categories
                or len(set(self.allowed_data_categories))
                   != len(self.allowed_data_categories)
                or any(type(value) is not str
                       or _CATEGORY.fullmatch(value) is None
                       for value in self.allowed_data_categories)
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.minimal_payload_policy_ref,
                           self.envelope_encoding_ref, self.token_estimator_ref,
                       ))
                or any(type(value) is not int or not 1 <= value <= 2_147_483_647
                       for value in (
                           self.envelope_encoding_version,
                           self.token_estimator_version,
                       ))):
            raise AIExecutionContentPlanError()


def content_plan_fingerprint(plan: AIExecutionContentPlan) -> bytes:
    if type(plan) is not AIExecutionContentPlan:
        raise AIExecutionContentPlanError()
    plan.__post_init__()
    context = plan.context
    return canonical_payload_fingerprint({
        "content_plan_id": str(plan.content_plan_id),
        "content_plan_version": plan.content_plan_version,
        "project_id": str(plan.project_id),
        "purpose_ref": plan.purpose_ref,
        "task_type": plan.task_type,
        "source_refs_fingerprint": plan.source_refs_fingerprint.hex(),
        "sources": [{
            "ordinal": source.ordinal,
            "resource_type": source.resource_type,
            "owner_module": source.owner_module,
            "object_type": source.object_type,
            "object_id": str(source.object_id),
            "version_id": str(source.version_id),
            "project_id": str(source.project_id),
            "content_kind": source.content_kind,
            "content_revision_id": str(source.content_revision_id),
            "content_object_id": str(source.content_object_id),
            "producer_ref": source.producer_ref,
            "producer_version": source.producer_version,
            "content_schema_ref": source.content_schema_ref,
            "selection_policy_ref": source.selection_policy_ref,
            "source_fingerprint": source.source_fingerprint.hex(),
            "content_fingerprint": source.content_fingerprint.hex(),
            "projection_fingerprint": source.projection_fingerprint.hex(),
            "content_size_bytes": source.content_size_bytes,
            "record_count": source.record_count,
        } for source in plan.sources],
        "prompt": {
            "prompt_policy_ref": plan.prompt.prompt_policy_ref,
            "prompt_policy_version": plan.prompt.prompt_policy_version,
            "prompt_template_id": str(plan.prompt.prompt_template_id),
            "prompt_version_no": plan.prompt.prompt_version_no,
            "system_template_hash": plan.prompt.system_template_hash,
            "user_template_hash": plan.prompt.user_template_hash,
            "provider_policy_ref": plan.prompt.provider_policy_ref,
            "output_schema_ref": plan.prompt.output_schema_ref,
            "schema_version": plan.prompt.schema_version,
            "rendering_policy_ref": plan.prompt.rendering_policy_ref,
            "rendering_policy_version": plan.prompt.rendering_policy_version,
        },
        "task_parameters_fingerprint": plan.task_parameters_fingerprint.hex(),
        "context": {
            "context_policy_ref": context.context_policy_ref,
            "mode": context.mode,
            "retrieval_run_id": (str(context.retrieval_run_id)
                                 if context.retrieval_run_id else None),
            "context_bundle_id": (str(context.context_bundle_id)
                                  if context.context_bundle_id else None),
            "context_bundle_fingerprint": (
                context.context_bundle_fingerprint.hex()
                if context.context_bundle_fingerprint else None
            ),
            "record_count": context.record_count,
            "content_size_bytes": context.content_size_bytes,
        },
        "ai_provider_id": str(plan.ai_provider_id),
        "provider_config_version_id": str(plan.provider_config_version_id),
        "ai_model_id": str(plan.ai_model_id),
        "provider_model_key": plan.provider_model_key,
        "model_revision": plan.model_revision,
        "data_region": plan.data_region,
        "allowed_data_categories": list(plan.allowed_data_categories),
        "minimal_payload_policy_ref": plan.minimal_payload_policy_ref,
        "envelope_encoding_ref": plan.envelope_encoding_ref,
        "envelope_encoding_version": plan.envelope_encoding_version,
        "token_estimator_ref": plan.token_estimator_ref,
        "token_estimator_version": plan.token_estimator_version,
    })


def require_content_plan_for_grant(
        grant: AITaskExecutionGrant,
        plan: AIExecutionContentPlan) -> AIExecutionContentPlan:
    """Prove that a persisted plan describes the exact execution grant."""

    if (type(grant) is not AITaskExecutionGrant
            or type(plan) is not AIExecutionContentPlan):
        raise AIExecutionContentPlanError("AI_EXECUTION_CONTENT_PLAN_NOT_AUTHORIZED")
    grant.__post_init__()
    plan.__post_init__()
    if (plan.project_id != grant.project_id
            or plan.content_plan_id != grant.content_plan_id
            or plan.purpose_ref != grant.purpose_ref
            or plan.task_type != grant.task_type
            or plan.source_refs_fingerprint != grant.source_refs_fingerprint
            or len(plan.sources) != len(grant.input_refs)
            or any(not _source_matches_input(source, input_ref)
                   for source, input_ref in zip(plan.sources, grant.input_refs))
            or plan.prompt.prompt_policy_ref != grant.prompt_policy_ref
            or plan.prompt.prompt_policy_version != grant.prompt_policy_version
            or plan.prompt.prompt_template_id != grant.prompt_template_id
            or plan.prompt.prompt_version_no != grant.prompt_version_no
            or plan.prompt.system_template_hash != grant.system_template_hash
            or plan.prompt.user_template_hash != grant.user_template_hash
            or plan.prompt.provider_policy_ref != grant.provider_policy_ref
            or plan.prompt.output_schema_ref != grant.output_schema_ref
            or plan.prompt.schema_version != grant.schema_version
            or plan.task_parameters_fingerprint
               != grant.task_parameters_fingerprint
            or plan.context.context_policy_ref != grant.context_policy_ref
            or plan.ai_provider_id != grant.ai_provider_id
            or plan.provider_config_version_id != grant.provider_config_version_id
            or plan.ai_model_id != grant.ai_model_id
            or plan.provider_model_key != grant.provider_model_key
            or plan.model_revision != grant.model_revision
            or plan.data_region != grant.data_region
            or plan.allowed_data_categories != tuple(sorted(
                grant.allowed_data_categories))
            or plan.minimal_payload_policy_ref
               != grant.minimal_payload_policy_ref):
        raise AIExecutionContentPlanError(
            "AI_EXECUTION_CONTENT_PLAN_NOT_AUTHORIZED",
        )
    return plan


def _source_matches_input(source: AIExecutionContentSourceIdentity,
                          input_ref: AITaskExecutionInputRef) -> bool:
    return (source.ordinal == input_ref.ordinal
            and source.resource_type == input_ref.resource_type
            and source.owner_module == input_ref.owner_module
            and source.object_type == input_ref.object_type
            and source.object_id == input_ref.object_id
            and source.version_id == input_ref.version_id
            and source.project_id == input_ref.project_id)


@dataclass(frozen=True, slots=True)
class AIExecutionContentIdentityQuery:
    """Least-authority request passed to a resource Owner during planning."""

    content_plan_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    purpose_ref: str
    minimal_payload_policy_ref: str
    selection_policy_ref: str

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.content_plan_id, self.project_id,
                    self.requested_by, self.trace_id,
                ))
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.purpose_ref, self.minimal_payload_policy_ref,
                           self.selection_policy_ref,
                       ))):
            raise AIExecutionContentPlanError()


class AIExecutionContentIdentityOwnerPort(Protocol):
    def resolve_identity(
        self,
        transaction: object,
        query: AIExecutionContentIdentityQuery,
        input_ref: AITaskExecutionInputRef,
    ) -> AIExecutionContentSourceIdentity: ...


@dataclass(frozen=True, slots=True)
class AIExecutionContentReadQuery:
    """Grant-derived current-authority request for one exact planned source."""

    content_plan_id: uuid.UUID
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    authorization_ref: uuid.UUID
    purpose_ref: str
    minimal_payload_policy_ref: str

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.content_plan_id, self.ai_task_id, self.project_id,
                    self.job_id, self.requested_by, self.trace_id,
                    self.authorization_ref,
                ))
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (
                           self.purpose_ref, self.minimal_payload_policy_ref,
                       ))):
            raise AIExecutionContentPlanError()


@dataclass(frozen=True, slots=True)
class AIExecutionContentProjection:
    """Short-lived minimum text projection; bytes are never represented."""

    source: AIExecutionContentSourceIdentity
    projection_schema_ref: str
    record_count: int
    content_utf8: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.source) is not AIExecutionContentSourceIdentity
                or type(self.projection_schema_ref) is not str
                or _REF.fullmatch(self.projection_schema_ref) is None
                or type(self.record_count) is not int
                or self.record_count != self.source.record_count
                or type(self.content_utf8) is not bytes
                or not 1 <= len(self.content_utf8) <= 100_000_000):
            raise AIExecutionContentPlanError()
        try:
            decoded = self.content_utf8.decode("utf-8")
        except UnicodeDecodeError:
            raise AIExecutionContentPlanError() from None
        if not decoded.strip():
            raise AIExecutionContentPlanError()
        if not hmac.compare_digest(
                hashlib.sha256(self.content_utf8).digest(),
                self.source.projection_fingerprint):
            raise AIExecutionContentPlanError()

    @property
    def projection_fingerprint(self) -> bytes:
        return hashlib.sha256(self.content_utf8).digest()


class AIExecutionContentReadOwnerPort(Protocol):
    def read_exact(
        self,
        transaction: object,
        query: AIExecutionContentReadQuery,
        source: AIExecutionContentSourceIdentity,
    ) -> AIExecutionContentProjection: ...
