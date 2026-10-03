"""Issue a complete, short-lived AI execution grant without projecting content."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.create_task import (
    AuthorizedEgressSnapshot, EgressAuthorizationOwnerError,
    EgressAuthorizationQuery,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant, AITaskExecutionGrantError, AITaskExecutionInputRef,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim, AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


@dataclass(frozen=True, slots=True)
class AITaskExecutionGrantMaterial:
    """AI-owned immutable metadata; no Job lease or source/Prompt content."""

    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
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
    approved_by: uuid.UUID
    approved_role: str
    approved_at: datetime
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    valid_until: datetime
    content_plan_ref: uuid.UUID | None = None


class AITaskExecutionGrantRepositoryPort(Protocol):
    def load(self, transaction: object, *, claim: AITaskExecutionClaim,
             now: datetime) -> AITaskExecutionGrantMaterial | None: ...


class AITaskExecutionGrantEgressOwnerPort(Protocol):
    def resolve_authorized(self, transaction: object, *,
                           query: EgressAuthorizationQuery) -> AuthorizedEgressSnapshot: ...


class AITaskExecutionGrantLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AITaskExecutionGrantIssuer:
    """Combine Jobs proof, AI metadata and live authorization in one short transaction."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: AITaskExecutionClaims,
                 repository: AITaskExecutionGrantRepositoryPort,
                 egress_owner: AITaskExecutionGrantEgressOwnerPort,
                 license_guard: AITaskExecutionGrantLicensePort) -> None:
        if any(value is None for value in (
            unit_of_work, claims, repository, egress_owner, license_guard,
        )):
            raise ValueError("AI Task execution grant dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository
        self._egress = egress_owner
        self._guard = license_guard

    def issue(self, *, job_id: uuid.UUID, fencing_token: int,
              worker_ref: str, now: datetime) -> AITaskExecutionGrant:
        if (type(job_id) is not uuid.UUID or not job_id.int
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AITaskExecutionGrantError()
        now = now.astimezone(timezone.utc)
        try:
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                material = self._repository.load(
                    transaction, claim=claim, now=now,
                )
                if type(material) is not AITaskExecutionGrantMaterial:
                    raise AITaskExecutionGrantError()
                self._require_claim(material, claim)
                current = self._egress.resolve_authorized(
                    transaction,
                    query=EgressAuthorizationQuery(
                        claim.egress_authorization_ref, claim.project_id,
                        material.task_type, claim.input_fingerprint, now,
                    ),
                )
                self._require_authorization(material, current, claim, now)
                self._guard.require_valid(trace_id=claim.trace_id)
                grant = AITaskExecutionGrant(
                    material.ai_task_id, material.project_id, material.job_id,
                    material.requested_by, material.trace_id, claim.attempt_no,
                    claim.fencing_token, material.task_type, material.input_refs,
                    material.source_refs_fingerprint, material.prompt_policy_ref,
                    material.prompt_policy_version, material.prompt_template_id,
                    material.prompt_version_no, material.system_template_hash,
                    material.user_template_hash, material.provider_policy_ref,
                    material.output_schema_ref, material.schema_version,
                    material.context_policy_ref,
                    material.task_parameters_fingerprint,
                    material.egress_snapshot_id, material.authorization_ref,
                    material.authorization_fingerprint, material.purpose_ref,
                    material.ai_provider_id, material.provider_config_version_id,
                    material.ai_model_id, material.provider_model_key,
                    material.model_revision, material.data_region,
                    material.allowed_data_categories,
                    material.approved_payload_fingerprint,
                    current.minimal_payload_policy_ref,
                    current.max_record_count, material.max_payload_bytes,
                    material.max_input_tokens, material.max_retry_attempts,
                    material.valid_until, material.content_plan_ref,
                )
            # Do not allow a license state change at the transaction boundary to
            # produce a usable grant. The network boundary will check again.
            self._guard.require_valid(trace_id=grant.trace_id)
            return grant
        except AITaskExecutionGrantError:
            raise
        except (JobLeaseError, EgressAuthorizationOwnerError, RuntimeLicenseError):
            raise AITaskExecutionGrantError() from None
        except Exception:
            raise AITaskExecutionGrantError() from None

    @staticmethod
    def _require_claim(material: AITaskExecutionGrantMaterial,
                       claim: AITaskExecutionClaim) -> None:
        if (material.ai_task_id != claim.ai_task_id
                or material.project_id != claim.project_id
                or material.job_id != claim.job_id
                or material.requested_by != claim.actor_id
                or material.trace_id != claim.trace_id
                or material.authorization_ref != claim.egress_authorization_ref
                or material.source_refs_fingerprint != claim.input_fingerprint
                or material.max_retry_attempts != claim.max_attempts
                or type(material.content_plan_ref) is not uuid.UUID
                or not material.content_plan_ref.int
                or claim.attempt_no > material.max_retry_attempts):
            raise AITaskExecutionGrantError()

    @staticmethod
    def _require_authorization(material: AITaskExecutionGrantMaterial,
                               current: AuthorizedEgressSnapshot,
                               claim: AITaskExecutionClaim,
                               now: datetime) -> None:
        if (type(current) is not AuthorizedEgressSnapshot
                or current.authorization_ref != material.authorization_ref
                or current.project_id != material.project_id
                or current.authorization_ref != claim.egress_authorization_ref
                or current.source_refs_fingerprint != material.source_refs_fingerprint
                or current.authorization_fingerprint
                != material.authorization_fingerprint
                or current.preview_payload_fingerprint
                != material.approved_payload_fingerprint
                or current.content_plan_ref != material.content_plan_ref
                or current.purpose_ref != material.purpose_ref
                or current.ai_provider_id != material.ai_provider_id
                or current.provider_config_version_id
                != material.provider_config_version_id
                or current.ai_model_id != material.ai_model_id
                or current.data_region != material.data_region
                or current.allowed_data_categories
                != material.allowed_data_categories
                or current.approved_by != material.approved_by
                or current.approved_role != material.approved_role
                or current.approved_at != material.approved_at
                or current.valid_until != material.valid_until
                or current.max_payload_bytes != material.max_payload_bytes
                or current.max_input_tokens != material.max_input_tokens
                or current.max_retry_attempts != material.max_retry_attempts
                or current.authorization_state != "AUTHORIZED"
                or now >= material.valid_until.astimezone(timezone.utc)):
            raise AITaskExecutionGrantError()
