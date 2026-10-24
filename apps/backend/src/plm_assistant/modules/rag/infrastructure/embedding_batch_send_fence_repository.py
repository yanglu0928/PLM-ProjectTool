"""PostgreSQL current-fact checks and PENDING-to-RUNNING batch fence."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from sqlalchemy import select

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
from plm_assistant.modules.rag.application.embedding_batch_send_fence import (
    RAGEmbeddingBatchPayloadProof,
    RAGEmbeddingBatchSendMaterial,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    DocumentChunkRow,
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
    EmbeddingIndexRow,
    IndexSourceChunkRow,
)


class SqlAlchemyRAGEmbeddingBatchSendFenceRepository:
    def mark_running(
        self, transaction: object, *, claim: RAGIndexBuildClaim,
        proof: RAGEmbeddingBatchPayloadProof, started_at: datetime,
    ) -> RAGEmbeddingBatchSendMaterial | None:
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        build = session.scalar(select(EmbeddingBuildRow).where(
            EmbeddingBuildRow.embedding_build_id == claim.embedding_build_id,
        ).with_for_update(of=EmbeddingBuildRow).execution_options(autoflush=False))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == claim.embedding_index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(autoflush=False))
        batch = session.scalar(select(EmbeddingBuildBatchRow).where(
            EmbeddingBuildBatchRow.embedding_build_id == claim.embedding_build_id,
            EmbeddingBuildBatchRow.batch_ordinal == proof.batch_ordinal,
        ).with_for_update(of=EmbeddingBuildBatchRow).execution_options(autoflush=False))
        if not self._build_and_batch_are_current(build, index, batch, claim, proof):
            return None

        authorization = session.scalar(select(AIEgressAuthorizationRow).where(
            AIEgressAuthorizationRow.authorization_id
            == batch.egress_authorization_ref,
        ).with_for_update(read=True, of=AIEgressAuthorizationRow)
         .execution_options(autoflush=False))
        model = session.scalar(select(AIModelRow).where(
            AIModelRow.ai_model_id == build.embedding_model_ref,
        ).with_for_update(read=True, of=AIModelRow)
         .execution_options(autoflush=False))
        if authorization is None or model is None:
            return None
        provider = session.scalar(select(AIProviderRow).where(
            AIProviderRow.ai_provider_id == authorization.ai_provider_id,
        ).with_for_update(read=True, of=AIProviderRow)
         .execution_options(autoflush=False))
        config = session.scalar(select(AIProviderConfigVersionRow).where(
            AIProviderConfigVersionRow.provider_config_version_id
            == authorization.provider_config_version_id,
            AIProviderConfigVersionRow.ai_provider_id
            == authorization.ai_provider_id,
        ).with_for_update(read=True, of=AIProviderConfigVersionRow)
         .execution_options(autoflush=False))
        if not self._route_is_current(
                authorization, model, provider, config, build, batch,
                claim, proof, started_at):
            return None

        sources = session.execute(select(
            IndexSourceChunkRow, DocumentChunkRow,
        ).join(
            DocumentChunkRow,
            DocumentChunkRow.chunk_id == IndexSourceChunkRow.chunk_id,
        ).where(
            IndexSourceChunkRow.embedding_index_id == claim.embedding_index_id,
            IndexSourceChunkRow.source_ordinal >= proof.source_first_ordinal,
            IndexSourceChunkRow.source_ordinal < (
                proof.source_first_ordinal + proof.source_record_count),
        ).order_by(IndexSourceChunkRow.source_ordinal)
         .with_for_update(read=True, of=(IndexSourceChunkRow, DocumentChunkRow))
         .execution_options(autoflush=False)).all()
        if not self._sources_are_current(
                sources, authorization, claim, proof):
            return None

        batch.batch_state = "RUNNING"
        batch.send_fencing_token = claim.fencing_token
        batch.started_at = started_at
        batch.lock_version += 1
        session.flush()
        return RAGEmbeddingBatchSendMaterial(
            batch.embedding_build_batch_id,
            batch.egress_authorization_ref,
            authorization.ai_provider_id,
            authorization.provider_config_version_id,
            authorization.ai_model_id,
            config.secret_ref,
            config.provider_kind,
            config.endpoint_policy_ref,
            config.data_region,
            config.egress_class,
            model.provider_model_key,
            model.model_revision,
            model.embedding_dimension,
            authorization.valid_until,
            batch.lock_version,
        )

    @staticmethod
    def _build_and_batch_are_current(build, index, batch,
                                     claim: RAGIndexBuildClaim,
                                     proof: RAGEmbeddingBatchPayloadProof) -> bool:
        return bool(
            build is not None and index is not None and batch is not None
            and build.embedding_index_id == claim.embedding_index_id
            and build.build_job_ref == claim.job_id
            and build.build_generation == claim.build_generation == 1
            and (build.scope, build.project_id) == (claim.scope, claim.project_id)
            and build.created_by == claim.actor_id
            and build.build_state == "RUNNING" and build.lock_version == 1
            and index.index_state == "BUILDING" and index.lock_version == 1
            and (index.scope, index.project_id) == (claim.scope, claim.project_id)
            and index.embedding_model_ref == build.embedding_model_ref
            and index.embedding_dimension == build.embedding_dimension
            and batch.batch_state == "PENDING" and batch.lock_version == 0
            and batch.send_fencing_token is None
            and batch.provider_request_ref is None and batch.error_code is None
            and batch.started_at is None and batch.completed_at is None
            and batch.source_first_ordinal == proof.source_first_ordinal
            and batch.source_record_count == proof.source_record_count
            and hmac.compare_digest(
                batch.source_batch_fingerprint, proof.source_batch_fingerprint)
            and hmac.compare_digest(
                batch.payload_fingerprint, proof.payload_fingerprint)
            and batch.payload_bytes == proof.payload_bytes
            and batch.input_tokens == proof.input_tokens
        )

    @staticmethod
    def _route_is_current(authorization, model, provider, config, build, batch,
                          claim: RAGIndexBuildClaim,
                          proof: RAGEmbeddingBatchPayloadProof,
                          started_at: datetime) -> bool:
        return bool(
            authorization.authorization_state == "AUTHORIZED"
            and authorization.valid_until > started_at
            and (authorization.scope, authorization.project_id)
            == (claim.scope, claim.project_id)
            and authorization.operation_type in {"INDEX_BUILD", "INDEX_REBUILD"}
            and authorization.ai_model_id == build.embedding_model_ref
            and authorization.max_retry_attempts == 1
            and authorization.max_record_count >= proof.source_record_count
            and authorization.max_payload_bytes >= proof.payload_bytes
            and authorization.max_input_tokens >= proof.input_tokens
            and hmac.compare_digest(
                authorization.source_refs_fingerprint,
                proof.source_batch_fingerprint)
            and hmac.compare_digest(
                authorization.payload_fingerprint, proof.payload_fingerprint)
            and model.ai_provider_id == authorization.ai_provider_id
            and model.model_kind == "EMBEDDING"
            and model.embedding_dimension == build.embedding_dimension
            and model.model_state == "AVAILABLE"
            and provider is not None and provider.provider_state == "ACTIVE"
            and provider.current_config_version_ref
            == authorization.provider_config_version_id
            and config is not None and config.can_embedding is True
            and config.data_region == authorization.data_region
        )

    @staticmethod
    def _sources_are_current(sources, authorization,
                             claim: RAGIndexBuildClaim,
                             proof: RAGEmbeddingBatchPayloadProof) -> bool:
        if len(sources) != proof.source_record_count:
            return False
        canonical: list[str] = []
        allowed = set(authorization.allowed_data_categories)
        for expected, (source, chunk) in enumerate(
                sources, proof.source_first_ordinal):
            if (source.source_ordinal != expected
                    or (source.scope, source.project_id)
                    != (claim.scope, claim.project_id)
                    or (chunk.scope, chunk.project_id)
                    != (claim.scope, claim.project_id)
                    or chunk.chunk_state != "ACTIVE"
                    or chunk.source_type not in allowed
                    or not hmac.compare_digest(
                        source.chunk_text_fingerprint, chunk.text_fingerprint)):
                return False
            canonical.append(
                f"{source.source_ordinal}:{source.chunk_id}:"
                f"{source.chunk_text_fingerprint.hex()}"
            )
        actual = hashlib.sha256("\n".join(canonical).encode("utf-8")).digest()
        return hmac.compare_digest(actual, proof.source_batch_fingerprint)
