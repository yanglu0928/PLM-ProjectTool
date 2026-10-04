"""Current PostgreSQL route facts for one unfenced Embedding Batch."""

from __future__ import annotations

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AIEmbeddingRouteMaterial,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIEgressAuthorizationRow,
)
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow,
    AIProviderRow,
)
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
    EmbeddingIndexRow,
)


class SqlAlchemyAIEmbeddingRouteRepository:
    def load_current(self, transaction: object, *, claim: RAGIndexBuildClaim,
                     envelope: AIEmbeddingEnvelope
                     ) -> AIEmbeddingRouteMaterial | None:
        if (type(claim) is not RAGIndexBuildClaim
                or type(envelope) is not AIEmbeddingEnvelope):
            return None
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        row = session.execute(select(
            EmbeddingBuildRow.build_job_ref,
            EmbeddingBuildRow.embedding_build_id,
            EmbeddingBuildBatchRow.embedding_build_batch_id,
            EmbeddingBuildRow.embedding_index_id,
            EmbeddingBuildBatchRow.egress_authorization_ref,
            EmbeddingBuildBatchRow.source_batch_fingerprint,
            EmbeddingBuildBatchRow.payload_fingerprint,
            EmbeddingBuildBatchRow.payload_bytes,
            EmbeddingBuildBatchRow.input_tokens,
            EmbeddingBuildBatchRow.source_record_count,
            AIEgressAuthorizationRow.ai_provider_id,
            AIEgressAuthorizationRow.provider_config_version_id,
            AIEgressAuthorizationRow.ai_model_id,
            AIProviderConfigVersionRow.provider_kind,
            AIProviderConfigVersionRow.endpoint_policy_ref,
            AIProviderConfigVersionRow.secret_ref,
            AIProviderConfigVersionRow.data_region,
            AIProviderConfigVersionRow.egress_class,
            AIModelRow.provider_model_key,
            AIModelRow.model_revision,
            AIModelRow.embedding_dimension,
            AIEgressAuthorizationRow.valid_until,
        ).join(
            EmbeddingIndexRow,
            EmbeddingIndexRow.embedding_index_id
            == EmbeddingBuildRow.embedding_index_id,
        ).join(
            EmbeddingBuildBatchRow,
            EmbeddingBuildBatchRow.embedding_build_id
            == EmbeddingBuildRow.embedding_build_id,
        ).join(
            AIEgressAuthorizationRow,
            AIEgressAuthorizationRow.authorization_id
            == EmbeddingBuildBatchRow.egress_authorization_ref,
        ).join(
            AIProviderRow,
            AIProviderRow.ai_provider_id == AIEgressAuthorizationRow.ai_provider_id,
        ).join(
            AIProviderConfigVersionRow,
            (AIProviderConfigVersionRow.provider_config_version_id
             == AIEgressAuthorizationRow.provider_config_version_id)
            & (AIProviderConfigVersionRow.ai_provider_id
               == AIEgressAuthorizationRow.ai_provider_id),
        ).join(
            AIModelRow,
            (AIModelRow.ai_model_id == AIEgressAuthorizationRow.ai_model_id)
            & (AIModelRow.ai_provider_id
               == AIEgressAuthorizationRow.ai_provider_id),
        ).where(
            EmbeddingBuildRow.embedding_build_id == claim.embedding_build_id,
            EmbeddingBuildRow.embedding_index_id == claim.embedding_index_id,
            EmbeddingBuildRow.build_job_ref == claim.job_id,
            EmbeddingBuildRow.scope == claim.scope,
            EmbeddingBuildRow.project_id == claim.project_id,
            EmbeddingBuildRow.created_by == claim.actor_id,
            EmbeddingBuildRow.build_generation == 1,
            EmbeddingBuildRow.build_state == "RUNNING",
            EmbeddingBuildRow.lock_version == 1,
            EmbeddingIndexRow.scope == claim.scope,
            EmbeddingIndexRow.project_id == claim.project_id,
            EmbeddingIndexRow.index_state == "BUILDING",
            EmbeddingIndexRow.lock_version == 1,
            EmbeddingBuildBatchRow.embedding_build_batch_id
            == envelope.embedding_build_batch_id,
            EmbeddingBuildBatchRow.batch_ordinal == envelope.batch_ordinal,
            EmbeddingBuildBatchRow.source_first_ordinal
            == envelope.source_first_ordinal,
            EmbeddingBuildBatchRow.batch_state == "PENDING",
            EmbeddingBuildBatchRow.lock_version == 0,
            EmbeddingBuildBatchRow.send_fencing_token.is_(None),
            AIEgressAuthorizationRow.scope == claim.scope,
            AIEgressAuthorizationRow.project_id == claim.project_id,
            AIEgressAuthorizationRow.operation_type.in_((
                "INDEX_BUILD", "INDEX_REBUILD",
            )),
            AIEgressAuthorizationRow.authorization_state == "AUTHORIZED",
            AIEgressAuthorizationRow.valid_until > func.clock_timestamp(),
            AIEgressAuthorizationRow.max_retry_attempts == 1,
            AIEgressAuthorizationRow.max_record_count
            >= EmbeddingBuildBatchRow.source_record_count,
            AIEgressAuthorizationRow.max_payload_bytes
            >= EmbeddingBuildBatchRow.payload_bytes,
            AIEgressAuthorizationRow.max_input_tokens
            >= EmbeddingBuildBatchRow.input_tokens,
            AIEgressAuthorizationRow.payload_fingerprint
            == EmbeddingBuildBatchRow.payload_fingerprint,
            AIEgressAuthorizationRow.source_refs_fingerprint
            == EmbeddingBuildBatchRow.source_batch_fingerprint,
            AIProviderRow.provider_state == "ACTIVE",
            AIProviderRow.current_config_version_ref
            == AIEgressAuthorizationRow.provider_config_version_id,
            AIProviderConfigVersionRow.provider_kind == "OPENAI_COMPATIBLE",
            AIProviderConfigVersionRow.can_embedding.is_(True),
            AIProviderConfigVersionRow.data_region
            == AIEgressAuthorizationRow.data_region,
            AIModelRow.model_kind == "EMBEDDING",
            AIModelRow.model_state == "AVAILABLE",
            AIModelRow.embedding_dimension
            == EmbeddingBuildRow.embedding_dimension,
            AIModelRow.ai_model_id == EmbeddingBuildRow.embedding_model_ref,
        ).with_for_update(of=[
            EmbeddingBuildRow, EmbeddingIndexRow, EmbeddingBuildBatchRow,
            AIEgressAuthorizationRow, AIProviderRow,
            AIProviderConfigVersionRow, AIModelRow,
        ]).execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None
        try:
            kind = ProviderKind(row.provider_kind)
        except ValueError:
            return None
        return AIEmbeddingRouteMaterial(
            row.build_job_ref, row.embedding_build_id,
            row.embedding_build_batch_id, row.embedding_index_id,
            row.egress_authorization_ref, bytes(row.source_batch_fingerprint),
            bytes(row.payload_fingerprint), row.payload_bytes,
            row.input_tokens, row.source_record_count,
            row.ai_provider_id, row.provider_config_version_id,
            row.ai_model_id, kind, row.endpoint_policy_ref,
            row.secret_ref, row.data_region, row.egress_class,
            row.provider_model_key, row.model_revision,
            row.embedding_dimension, row.valid_until,
        )
