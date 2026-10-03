"""Final post-Begin authorization before an AI Provider Adapter may send."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

from .create_task import (
    AuthorizedEgressSnapshot,
    EgressAuthorizationOwnerError,
    EgressAuthorizationQuery,
)
from .provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderSendProof,
    provider_route_fingerprint,
    require_provider_send,
)
from .provider_execution_policy import AIProviderExecutionPolicyRegistry
from .task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionGrantError,
    execution_grant_fingerprint,
    require_payload_plan,
)
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AIProviderPreSendError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_SEND_NOT_AUTHORIZED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIProviderExecutionRouteMaterial:
    ai_task_id: uuid.UUID
    ai_invocation_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    attempt_no: int
    egress_snapshot_id: uuid.UUID
    authorization_ref: uuid.UUID
    content_plan_id: uuid.UUID
    request_payload_fingerprint: bytes
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    provider_kind: ProviderKind
    endpoint_policy_ref: str
    secret_ref: uuid.UUID
    data_region: str
    egress_class: str
    provider_model_key: str
    model_revision: str


@dataclass(frozen=True, slots=True)
class AuthorizedAIProviderSend:
    route: AIProviderExecutionRoute
    proof: AIProviderSendProof

    def __post_init__(self) -> None:
        if (type(self.route) is not AIProviderExecutionRoute
                or type(self.proof) is not AIProviderSendProof):
            raise AIProviderPreSendError()


class AIProviderExecutionRouteRepositoryPort(Protocol):
    def load_current(
        self, transaction: object, *, claim: AITaskExecutionClaim,
        ai_invocation_id: uuid.UUID,
    ) -> AIProviderExecutionRouteMaterial | None: ...


class AIProviderExecutionEgressOwnerPort(Protocol):
    def resolve_authorized(
        self, transaction: object, *, query: EgressAuthorizationQuery,
    ) -> AuthorizedEgressSnapshot: ...


class AIProviderExecutionSecretProofPort(Protocol):
    def active_provider_key_version(
        self, transaction: object, *, secret_ref: uuid.UUID,
    ) -> uuid.UUID | None: ...


class AIProviderExecutionLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIProviderPreSendService:
    """Recheck mutable facts in one short transaction; perform no network I/O."""

    def __init__(
        self, *, unit_of_work: Callable[[], object], claims: AITaskExecutionClaims,
        repository: AIProviderExecutionRouteRepositoryPort,
        egress_owner: AIProviderExecutionEgressOwnerPort,
        secret_proof: AIProviderExecutionSecretProofPort,
        policies: AIProviderExecutionPolicyRegistry,
        license_guard: AIProviderExecutionLicensePort,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, claims, repository, egress_owner, secret_proof,
            policies, license_guard,
        )):
            raise ValueError("AI Provider pre-send dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository
        self._egress = egress_owner
        self._secrets = secret_proof
        self._policies = policies
        self._guard = license_guard

    def authorize(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str, now: datetime,
    ) -> AuthorizedAIProviderSend:
        if (type(prepared) is not PreparedAITaskInvocation
                or type(begun) is not BegunAITaskInvocation
                or type(job_id) is not uuid.UUID or not job_id.int
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AIProviderPreSendError()
        now = now.astimezone(timezone.utc)
        try:
            prepared.__post_init__()
            begun.__post_init__()
            prepared_fingerprint = execution_grant_fingerprint(prepared.grant)
            if (not hmac.compare_digest(
                    prepared_fingerprint,
                    execution_grant_fingerprint(begun.grant))
                    or job_id != prepared.grant.job_id
                    or fencing_token != prepared.grant.fencing_token):
                raise AIProviderPreSendError()
            require_payload_plan(prepared.grant, prepared.payload_plan, now=now)
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                self._require_claim(prepared.grant, claim)
                material = self._repository.load_current(
                    transaction, claim=claim,
                    ai_invocation_id=begun.ai_invocation_id,
                )
                if type(material) is not AIProviderExecutionRouteMaterial:
                    raise AIProviderPreSendError()
                self._require_material(prepared.grant, begun, material)
                current = self._egress.resolve_authorized(
                    transaction,
                    query=EgressAuthorizationQuery(
                        prepared.grant.authorization_ref,
                        prepared.grant.project_id,
                        prepared.grant.task_type,
                        prepared.grant.source_refs_fingerprint,
                        now,
                    ),
                )
                self._require_authorization(prepared.grant, current)
                secret_version = self._secrets.active_provider_key_version(
                    transaction, secret_ref=material.secret_ref,
                )
                if type(secret_version) is not uuid.UUID or not secret_version.int:
                    raise AIProviderPreSendError()
                policy = self._policies.resolve(
                    reference=material.endpoint_policy_ref,
                    provider_kind=material.provider_kind,
                    data_region=material.data_region,
                    egress_class=material.egress_class,
                    provider_model_key=material.provider_model_key,
                )
                route = AIProviderExecutionRoute(
                    material.ai_provider_id,
                    material.provider_config_version_id,
                    material.ai_model_id,
                    material.provider_kind,
                    material.endpoint_policy_ref,
                    policy.endpoint_url,
                    material.secret_ref,
                    secret_version,
                    material.provider_model_key,
                    material.model_revision,
                    material.data_region,
                    material.egress_class,
                    policy.max_response_bytes,
                    policy.connect_timeout_seconds,
                    policy.read_timeout_seconds,
                    policy.total_timeout_seconds,
                )
                proof = AIProviderSendProof(
                    prepared.grant.ai_task_id,
                    begun.ai_invocation_id,
                    prepared.grant.job_id,
                    prepared.grant.attempt_no,
                    prepared.grant.fencing_token,
                    prepared.grant.content_plan_id,
                    prepared.grant.authorization_ref,
                    prepared_fingerprint,
                    provider_route_fingerprint(route),
                    prepared.envelope.payload_fingerprint,
                    prepared.envelope.payload_bytes,
                    prepared.envelope.input_tokens,
                    prepared.grant.valid_until,
                )
                self._guard.require_valid(trace_id=prepared.grant.trace_id)
                result = AuthorizedAIProviderSend(route, proof)
            self._guard.require_valid(trace_id=prepared.grant.trace_id)
            require_provider_send(
                result.proof, result.route, prepared.envelope, now=now,
            )
            return result
        except AIProviderPreSendError:
            raise
        except (
            AITaskExecutionGrantError, AIProviderExecutionError,
            EgressAuthorizationOwnerError, JobLeaseError, RuntimeLicenseError,
        ):
            raise AIProviderPreSendError() from None
        except Exception:
            raise AIProviderPreSendError() from None

    @staticmethod
    def _require_claim(
        grant: AITaskExecutionGrant, claim: AITaskExecutionClaim,
    ) -> None:
        if (claim.ai_task_id != grant.ai_task_id
                or claim.project_id != grant.project_id
                or claim.job_id != grant.job_id
                or claim.actor_id != grant.requested_by
                or claim.trace_id != grant.trace_id
                or claim.egress_authorization_ref != grant.authorization_ref
                or not hmac.compare_digest(
                    claim.input_fingerprint, grant.source_refs_fingerprint)
                or claim.attempt_no != grant.attempt_no
                or claim.fencing_token != grant.fencing_token
                or claim.max_attempts != grant.max_retry_attempts):
            raise AIProviderPreSendError()

    @staticmethod
    def _require_material(
        grant: AITaskExecutionGrant, begun: BegunAITaskInvocation,
        value: AIProviderExecutionRouteMaterial,
    ) -> None:
        if (value.ai_task_id != grant.ai_task_id
                or value.ai_invocation_id != begun.ai_invocation_id
                or value.project_id != grant.project_id
                or value.job_id != grant.job_id
                or value.attempt_no != grant.attempt_no
                or value.egress_snapshot_id != grant.egress_snapshot_id
                or value.authorization_ref != grant.authorization_ref
                or value.content_plan_id != grant.content_plan_id
                or not hmac.compare_digest(
                    value.request_payload_fingerprint,
                    grant.approved_payload_fingerprint)
                or value.ai_provider_id != grant.ai_provider_id
                or value.provider_config_version_id
                != grant.provider_config_version_id
                or value.ai_model_id != grant.ai_model_id
                or value.provider_model_key != grant.provider_model_key
                or value.model_revision != grant.model_revision
                or value.data_region != grant.data_region):
            raise AIProviderPreSendError()

    @staticmethod
    def _require_authorization(
        grant: AITaskExecutionGrant, current: AuthorizedEgressSnapshot,
    ) -> None:
        if (type(current) is not AuthorizedEgressSnapshot
                or current.authorization_ref != grant.authorization_ref
                or current.project_id != grant.project_id
                or current.purpose_ref != grant.purpose_ref
                or current.ai_provider_id != grant.ai_provider_id
                or current.provider_config_version_id
                != grant.provider_config_version_id
                or current.ai_model_id != grant.ai_model_id
                or current.data_region != grant.data_region
                or current.allowed_data_categories
                != grant.allowed_data_categories
                or not hmac.compare_digest(
                    current.authorization_fingerprint,
                    grant.authorization_fingerprint)
                or not hmac.compare_digest(
                    current.preview_payload_fingerprint,
                    grant.approved_payload_fingerprint)
                or not hmac.compare_digest(
                    current.source_refs_fingerprint,
                    grant.source_refs_fingerprint)
                or current.valid_until != grant.valid_until
                or current.minimal_payload_policy_ref
                != grant.minimal_payload_policy_ref
                or current.max_record_count != grant.max_record_count
                or current.max_payload_bytes != grant.max_payload_bytes
                or current.max_input_tokens != grant.max_input_tokens
                or current.max_retry_attempts != grant.max_retry_attempts
                or current.authorization_state != "AUTHORIZED"
                or current.content_plan_ref != grant.content_plan_id):
            raise AIProviderPreSendError()
