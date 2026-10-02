"""Non-content execution grant and deterministic payload-plan proof contract."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)


_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_OWNER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OBJECT = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_REGION = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class AITaskExecutionGrantError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_EXECUTION_NOT_ADMITTED") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


def _utc(value: object) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class AITaskExecutionInputRef:
    ordinal: int
    resource_type: str
    owner_module: str
    object_type: str
    object_id: uuid.UUID
    version_id: uuid.UUID
    project_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.ordinal) is not int or not 1 <= self.ordinal <= 1000
                or self.resource_type != "DOC-02"
                or type(self.owner_module) is not str
                or _OWNER.fullmatch(self.owner_module) is None
                or type(self.object_type) is not str
                or _OBJECT.fullmatch(self.object_type) is None
                or not all(_id(value) for value in (
                    self.object_id, self.version_id, self.project_id,
                ))):
            raise AITaskExecutionGrantError()


@dataclass(frozen=True, slots=True)
class AITaskExecutionGrant:
    """Short-lived metadata proof; never contains Prompt, input, Key or response text."""

    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    attempt_no: int
    fencing_token: int
    task_type: str
    input_refs: tuple[AITaskExecutionInputRef, ...]
    source_refs_fingerprint: bytes = field(repr=False)
    prompt_policy_ref: str
    prompt_policy_version: int
    prompt_template_id: uuid.UUID
    prompt_version_no: int
    system_template_hash: str
    user_template_hash: str
    provider_policy_ref: str
    output_schema_ref: str
    schema_version: int
    context_policy_ref: str
    task_parameters_fingerprint: bytes = field(repr=False)
    egress_snapshot_id: uuid.UUID
    authorization_ref: uuid.UUID
    authorization_fingerprint: bytes = field(repr=False)
    purpose_ref: str
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    provider_model_key: str
    model_revision: str
    data_region: str
    allowed_data_categories: tuple[str, ...]
    approved_payload_fingerprint: bytes = field(repr=False)
    max_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    valid_until: datetime

    def __post_init__(self) -> None:
        identifiers = (
            self.ai_task_id, self.project_id, self.job_id, self.requested_by,
            self.trace_id, self.prompt_template_id, self.egress_snapshot_id,
            self.authorization_ref, self.ai_provider_id,
            self.provider_config_version_id, self.ai_model_id,
        )
        refs = (
            self.prompt_policy_ref, self.provider_policy_ref,
            self.output_schema_ref, self.context_policy_ref, self.purpose_ref,
        )
        hashes = (self.system_template_hash, self.user_template_hash)
        if (not all(_id(value) for value in identifiers)
                or type(self.attempt_no) is not int
                or not 1 <= self.attempt_no <= 10
                or type(self.fencing_token) is not int
                or not 1 <= self.fencing_token <= 9_223_372_036_854_775_807
                or type(self.task_type) is not str or not self.task_type
                or type(self.input_refs) is not tuple or not self.input_refs
                or any(type(item) is not AITaskExecutionInputRef
                       or item.ordinal != index or item.project_id != self.project_id
                       for index, item in enumerate(self.input_refs, 1))
                or not _digest(self.source_refs_fingerprint)
                or not _digest(self.task_parameters_fingerprint)
                or not _digest(self.authorization_fingerprint)
                or not _digest(self.approved_payload_fingerprint)
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in refs)
                or any(type(value) is not str
                       or re.fullmatch(r"[0-9a-f]{64}", value) is None
                       for value in hashes)
                or type(self.prompt_policy_version) is not int
                or not 1 <= self.prompt_policy_version <= 2_147_483_647
                or type(self.prompt_version_no) is not int or self.prompt_version_no < 1
                or type(self.schema_version) is not int
                or not 1 <= self.schema_version <= 2_147_483_647
                or type(self.provider_model_key) is not str
                or _MODEL.fullmatch(self.provider_model_key) is None
                or type(self.model_revision) is not str
                or _MODEL.fullmatch(self.model_revision) is None
                or type(self.data_region) is not str
                or _REGION.fullmatch(self.data_region) is None
                or type(self.allowed_data_categories) is not tuple
                or not 1 <= len(self.allowed_data_categories) <= 64
                or len(set(self.allowed_data_categories))
                   != len(self.allowed_data_categories)
                or any(type(value) is not str
                       or _CATEGORY.fullmatch(value) is None
                       for value in self.allowed_data_categories)
                or type(self.max_record_count) is not int
                or not 1 <= self.max_record_count <= 1_000_000_000
                or type(self.max_payload_bytes) is not int
                or not 1 <= self.max_payload_bytes <= 1_073_741_824
                or type(self.max_input_tokens) is not int
                or not 1 <= self.max_input_tokens <= 1_048_576
                or type(self.max_retry_attempts) is not int
                or not 1 <= self.max_retry_attempts <= 10
                or self.attempt_no > self.max_retry_attempts
                or not _utc(self.valid_until)):
            raise AITaskExecutionGrantError()


def execution_grant_fingerprint(grant: AITaskExecutionGrant) -> bytes:
    if type(grant) is not AITaskExecutionGrant:
        raise AITaskExecutionGrantError()
    grant.__post_init__()
    return canonical_payload_fingerprint({
        "ai_task_id": str(grant.ai_task_id), "project_id": str(grant.project_id),
        "job_id": str(grant.job_id), "requested_by": str(grant.requested_by),
        "trace_id": str(grant.trace_id), "attempt_no": grant.attempt_no,
        "fencing_token": grant.fencing_token, "task_type": grant.task_type,
        "input_refs": [{
            "ordinal": item.ordinal, "resource_type": item.resource_type,
            "owner_module": item.owner_module, "object_type": item.object_type,
            "object_id": str(item.object_id), "version_id": str(item.version_id),
            "project_id": str(item.project_id),
        } for item in grant.input_refs],
        "source_refs_fingerprint": grant.source_refs_fingerprint.hex(),
        "prompt_policy_ref": grant.prompt_policy_ref,
        "prompt_policy_version": grant.prompt_policy_version,
        "prompt_template_id": str(grant.prompt_template_id),
        "prompt_version_no": grant.prompt_version_no,
        "system_template_hash": grant.system_template_hash,
        "user_template_hash": grant.user_template_hash,
        "provider_policy_ref": grant.provider_policy_ref,
        "output_schema_ref": grant.output_schema_ref,
        "schema_version": grant.schema_version,
        "context_policy_ref": grant.context_policy_ref,
        "task_parameters_fingerprint": grant.task_parameters_fingerprint.hex(),
        "egress_snapshot_id": str(grant.egress_snapshot_id),
        "authorization_ref": str(grant.authorization_ref),
        "authorization_fingerprint": grant.authorization_fingerprint.hex(),
        "purpose_ref": grant.purpose_ref,
        "ai_provider_id": str(grant.ai_provider_id),
        "provider_config_version_id": str(grant.provider_config_version_id),
        "ai_model_id": str(grant.ai_model_id),
        "provider_model_key": grant.provider_model_key,
        "model_revision": grant.model_revision,
        "data_region": grant.data_region,
        "allowed_data_categories": list(grant.allowed_data_categories),
        "approved_payload_fingerprint": grant.approved_payload_fingerprint.hex(),
        "max_record_count": grant.max_record_count,
        "max_payload_bytes": grant.max_payload_bytes,
        "max_input_tokens": grant.max_input_tokens,
        "max_retry_attempts": grant.max_retry_attempts,
        "valid_until": grant.valid_until.isoformat(),
    })


@dataclass(frozen=True, slots=True)
class AITaskPayloadPlanProof:
    """No-content proof emitted by the future deterministic envelope builder."""

    ai_task_id: uuid.UUID
    job_id: uuid.UUID
    attempt_no: int
    grant_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    record_count: int
    payload_bytes: int
    input_tokens: int
    context_bundle_fingerprint: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (self.ai_task_id, self.job_id))
                or type(self.attempt_no) is not int or not 1 <= self.attempt_no <= 10
                or not all(_digest(value) for value in (
                    self.grant_fingerprint, self.source_refs_fingerprint,
                    self.payload_fingerprint,
                ))
                or (self.context_bundle_fingerprint is not None
                    and not _digest(self.context_bundle_fingerprint))
                or type(self.record_count) is not int or self.record_count < 1
                or type(self.payload_bytes) is not int or self.payload_bytes < 1
                or type(self.input_tokens) is not int or self.input_tokens < 1):
            raise AITaskExecutionGrantError("AI_TASK_PAYLOAD_PLAN_INVALID")


def require_payload_plan(grant: AITaskExecutionGrant,
                         proof: AITaskPayloadPlanProof,
                         *, now: datetime) -> AITaskPayloadPlanProof:
    if type(grant) is not AITaskExecutionGrant or type(proof) is not AITaskPayloadPlanProof:
        raise AITaskExecutionGrantError("AI_TASK_PAYLOAD_PLAN_INVALID")
    grant.__post_init__()
    proof.__post_init__()
    if (not _utc(now) or now >= grant.valid_until
            or proof.ai_task_id != grant.ai_task_id
            or proof.job_id != grant.job_id
            or proof.attempt_no != grant.attempt_no
            or proof.grant_fingerprint != execution_grant_fingerprint(grant)
            or proof.source_refs_fingerprint != grant.source_refs_fingerprint
            or proof.payload_fingerprint != grant.approved_payload_fingerprint
            or proof.record_count > grant.max_record_count
            or proof.payload_bytes > grant.max_payload_bytes
            or proof.input_tokens > grant.max_input_tokens):
        raise AITaskExecutionGrantError("AI_TASK_PAYLOAD_PLAN_NOT_AUTHORIZED")
    return proof
