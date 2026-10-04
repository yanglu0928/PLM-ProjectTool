"""RAG-owned bridge from AI Embedding send proof to the durable Batch fence."""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
    AIEmbeddingExecutionError,
    require_embedding_send,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.send_embedding_request import (
    AIEmbeddingBatchFenceError,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind

from .embedding_batch_send_fence import (
    FencedRAGEmbeddingBatch,
    RAGEmbeddingBatchPayloadProof,
    RAGEmbeddingBatchSendFenceError,
    RAGEmbeddingBatchSendFenceService,
)


class RAGEmbeddingAISendFenceError(AIEmbeddingBatchFenceError):
    def __init__(self, *, committed: bool = False) -> None:
        super().__init__(committed=committed)


class RAGEmbeddingAISendFence:
    def __init__(self, service: RAGEmbeddingBatchSendFenceService) -> None:
        if service is None:
            raise ValueError("RAG Embedding Batch fence required")
        self._service = service

    def fence(self, *, envelope: AIEmbeddingEnvelope,
              send: AuthorizedAIEmbeddingSend, job_id: uuid.UUID,
              fencing_token: int, worker_ref: str,
              now: datetime) -> FencedRAGEmbeddingBatch:
        committed = False
        try:
            if (type(envelope) is not AIEmbeddingEnvelope
                    or type(send) is not AuthorizedAIEmbeddingSend
                    or not isinstance(now, datetime) or now.tzinfo is None
                    or now.utcoffset() is None):
                raise RAGEmbeddingAISendFenceError()
            now = now.astimezone(timezone.utc)
            require_embedding_send(send.proof, send.route, envelope, now=now)
            proof = RAGEmbeddingBatchPayloadProof(
                envelope.embedding_build_id, envelope.embedding_index_id,
                envelope.batch_ordinal, envelope.source_first_ordinal,
                envelope.record_count, envelope.source_refs_fingerprint,
                envelope.payload_fingerprint, envelope.payload_bytes,
                envelope.input_tokens,
            )
            result = self._service.fence(
                proof=proof, job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref,
            )
            committed = True
            self._require_result(result, envelope, send)
            return result
        except RAGEmbeddingAISendFenceError:
            raise
        except RAGEmbeddingBatchSendFenceError as exc:
            raise RAGEmbeddingAISendFenceError(
                committed=exc.committed,
            ) from None
        except AIEmbeddingExecutionError:
            raise RAGEmbeddingAISendFenceError(committed=committed) from None
        except Exception:
            raise RAGEmbeddingAISendFenceError(committed=committed) from None

    @staticmethod
    def _require_result(result: FencedRAGEmbeddingBatch,
                        envelope: AIEmbeddingEnvelope,
                        send: AuthorizedAIEmbeddingSend) -> None:
        if type(result) is not FencedRAGEmbeddingBatch:
            raise RAGEmbeddingAISendFenceError(committed=True)
        material, route, proof = result.material, send.route, send.proof
        kind = (route.provider_kind.value
                if isinstance(route.provider_kind, ProviderKind) else None)
        if (result.claim.job_id != proof.job_id
                or result.claim.trace_id != proof.trace_id
                or result.claim.actor_id != proof.actor_id
                or result.claim.scope != proof.scope
                or result.claim.project_id != proof.project_id
                or material.embedding_build_batch_id
                != envelope.embedding_build_batch_id
                or material.egress_authorization_ref
                != proof.egress_authorization_ref
                or material.ai_provider_id != route.ai_provider_id
                or material.provider_config_version_id
                != route.provider_config_version_id
                or material.ai_model_id != route.ai_model_id
                or material.secret_ref != route.secret_ref
                or material.provider_kind != kind
                or material.endpoint_policy_ref != route.endpoint_policy_ref
                or material.data_region != route.data_region
                or material.egress_class != route.egress_class
                or material.provider_model_key != route.provider_model_key
                or material.model_revision != route.model_revision
                or material.embedding_dimension != envelope.embedding_dimension
                or not hmac.compare_digest(
                    result.proof.payload_fingerprint,
                    envelope.payload_fingerprint)):
            raise RAGEmbeddingAISendFenceError(committed=True)
