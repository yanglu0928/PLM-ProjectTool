"""Final current-fact authorization for one RAG Embedding Provider send."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

from .embedding_execution_contract import (
    AIEmbeddingEnvelope,
    AIEmbeddingExecutionError,
    AIEmbeddingSendProof,
    require_embedding_send,
)
from .provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    provider_route_fingerprint,
)
from .provider_execution_policy import AIProviderExecutionPolicyRegistry


class AIEmbeddingPreSendError(RuntimeError):
    def __init__(self, code: str = "AI_EMBEDDING_SEND_NOT_AUTHORIZED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIEmbeddingRouteMaterial:
    job_id: uuid.UUID
    embedding_build_id: uuid.UUID
    embedding_build_batch_id: uuid.UUID
    embedding_index_id: uuid.UUID
    egress_authorization_ref: uuid.UUID
    source_refs_fingerprint: bytes
    payload_fingerprint: bytes
    payload_bytes: int
    input_tokens: int
    source_record_count: int
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
    embedding_dimension: int
    valid_until: datetime

    def __post_init__(self) -> None:
        identifiers = (
            self.job_id, self.embedding_build_id,
            self.embedding_build_batch_id, self.embedding_index_id,
            self.egress_authorization_ref, self.ai_provider_id,
            self.provider_config_version_id, self.ai_model_id, self.secret_ref,
        )
        strings = (
            self.endpoint_policy_ref, self.data_region, self.egress_class,
            self.provider_model_key, self.model_revision,
        )
        if (any(type(value) is not uuid.UUID or not value.int
                for value in identifiers)
                or any(type(value) is not bytes or len(value) != 32 for value in (
                    self.source_refs_fingerprint, self.payload_fingerprint,
                ))
                or type(self.payload_bytes) is not int
                or not 1 <= self.payload_bytes <= 100_000_000
                or type(self.input_tokens) is not int
                or not 1 <= self.input_tokens <= 1_048_576
                or type(self.source_record_count) is not int
                or not 1 <= self.source_record_count <= 1_000
                or self.provider_kind is not ProviderKind.OPENAI_COMPATIBLE
                or any(type(value) is not str or not value for value in strings)
                or self.embedding_dimension not in {768, 1024}
                or not isinstance(self.valid_until, datetime)
                or self.valid_until.tzinfo is None
                or self.valid_until.utcoffset() is None):
            raise AIEmbeddingPreSendError()


@dataclass(frozen=True, slots=True)
class AuthorizedAIEmbeddingSend:
    route: AIProviderExecutionRoute
    proof: AIEmbeddingSendProof

    def __post_init__(self) -> None:
        if (type(self.route) is not AIProviderExecutionRoute
                or type(self.proof) is not AIEmbeddingSendProof):
            raise AIEmbeddingPreSendError()


class AIEmbeddingRouteRepositoryPort(Protocol):
    def load_current(self, transaction: object, *, claim: RAGIndexBuildClaim,
                     envelope: AIEmbeddingEnvelope
                     ) -> AIEmbeddingRouteMaterial | None: ...


class AIEmbeddingSecretProofPort(Protocol):
    def active_provider_key_version(self, transaction: object, *,
                                    secret_ref: uuid.UUID
                                    ) -> uuid.UUID | None: ...


class AIEmbeddingLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIEmbeddingPreSendService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGIndexBuildClaims,
                 repository: AIEmbeddingRouteRepositoryPort,
                 secret_proof: AIEmbeddingSecretProofPort,
                 policies: AIProviderExecutionPolicyRegistry,
                 license_guard: AIEmbeddingLicensePort) -> None:
        if any(value is None for value in (
                unit_of_work, claims, repository, secret_proof, policies,
                license_guard)):
            raise ValueError("AI Embedding pre-send dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository
        self._secrets = secret_proof
        self._policies = policies
        self._guard = license_guard

    def authorize(self, *, envelope: AIEmbeddingEnvelope,
                  job_id: uuid.UUID, fencing_token: int,
                  worker_ref: str, now: datetime) -> AuthorizedAIEmbeddingSend:
        if (type(envelope) is not AIEmbeddingEnvelope
                or type(job_id) is not uuid.UUID or not job_id.int
                or type(fencing_token) is not int or fencing_token < 1
                or type(worker_ref) is not str or not worker_ref.strip()
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AIEmbeddingPreSendError()
        now = now.astimezone(timezone.utc)
        try:
            envelope.__post_init__()
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                if (claim.job_id != job_id
                        or claim.fencing_token != fencing_token
                        or claim.embedding_build_id != envelope.embedding_build_id
                        or claim.embedding_index_id != envelope.embedding_index_id):
                    raise AIEmbeddingPreSendError()
                material = self._repository.load_current(
                    transaction, claim=claim, envelope=envelope,
                )
                if type(material) is not AIEmbeddingRouteMaterial:
                    raise AIEmbeddingPreSendError()
                material.__post_init__()
                self._require_material(claim, envelope, material)
                secret_version = self._secrets.active_provider_key_version(
                    transaction, secret_ref=material.secret_ref,
                )
                if type(secret_version) is not uuid.UUID or not secret_version.int:
                    raise AIEmbeddingPreSendError()
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
                    material.ai_model_id, material.provider_kind,
                    material.endpoint_policy_ref, policy.endpoint_url,
                    material.secret_ref, secret_version,
                    material.provider_model_key, material.model_revision,
                    material.data_region, material.egress_class,
                    policy.max_response_bytes,
                    policy.connect_timeout_seconds,
                    policy.read_timeout_seconds,
                    policy.total_timeout_seconds,
                )
                valid_until = min(
                    material.valid_until.astimezone(timezone.utc),
                    claim.lease_expires_at.astimezone(timezone.utc) - timedelta(
                        seconds=policy.total_timeout_seconds + 2,
                    ),
                )
                if now >= valid_until or claim.observed_at >= valid_until:
                    raise AIEmbeddingPreSendError()
                proof = AIEmbeddingSendProof(
                    claim.job_id, claim.embedding_build_id,
                    material.embedding_build_batch_id,
                    material.egress_authorization_ref, claim.trace_id,
                    claim.actor_id, claim.scope, claim.project_id,
                    claim.fencing_token,
                    provider_route_fingerprint(route),
                    envelope.source_refs_fingerprint,
                    envelope.payload_fingerprint, envelope.payload_bytes,
                    envelope.input_tokens, valid_until,
                )
                self._guard.require_valid(trace_id=claim.trace_id)
                result = AuthorizedAIEmbeddingSend(route, proof)
            self._guard.require_valid(trace_id=claim.trace_id)
            require_embedding_send(result.proof, result.route, envelope, now=now)
            return result
        except AIEmbeddingPreSendError:
            raise
        except (AIEmbeddingExecutionError, AIProviderExecutionError,
                JobLeaseError, RuntimeLicenseError):
            raise AIEmbeddingPreSendError() from None
        except Exception:
            raise AIEmbeddingPreSendError() from None

    @staticmethod
    def _require_material(claim: RAGIndexBuildClaim,
                          envelope: AIEmbeddingEnvelope,
                          value: AIEmbeddingRouteMaterial) -> None:
        if (value.job_id != claim.job_id
                or value.embedding_build_id != claim.embedding_build_id
                or value.embedding_index_id != claim.embedding_index_id
                or value.embedding_index_id != envelope.embedding_index_id
                or value.embedding_build_batch_id
                != envelope.embedding_build_batch_id
                or not hmac.compare_digest(
                    value.source_refs_fingerprint,
                    envelope.source_refs_fingerprint)
                or not hmac.compare_digest(
                    value.payload_fingerprint, envelope.payload_fingerprint)
                or value.payload_bytes != envelope.payload_bytes
                or value.input_tokens != envelope.input_tokens
                or value.source_record_count != envelope.record_count
                or value.provider_model_key != envelope.provider_model_key
                or value.model_revision != envelope.model_revision
                or value.embedding_dimension != envelope.embedding_dimension):
            raise AIEmbeddingPreSendError()
