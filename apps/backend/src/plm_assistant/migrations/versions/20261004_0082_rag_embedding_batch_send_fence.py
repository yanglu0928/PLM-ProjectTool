"""Add the durable RAG embedding batch pre-network send fence.

Revision ID: 20261004_0082
Revises: 20261004_0081
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0082"
down_revision = "20261004_0081"
branch_labels = None
depends_on = None


_BATCH_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build_batch()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    build_row plm.rag_embedding_builds%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
    lease_row plm.job_leases%ROWTYPE;
    attempt_row plm.job_attempts%ROWTYPE;
    authz_row plm.ai_egress_authorizations%ROWTYPE;
    model_row plm.ai_models%ROWTYPE;
    provider_row plm.ai_providers%ROWTYPE;
    config_row plm.ai_provider_config_versions%ROWTYPE;
    source_count bigint;
    source_is_current boolean;
    current_source_fingerprint bytea;
    now_at_db timestamptz;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'RAG EmbeddingBuildBatch history is retained'; END IF;
    SELECT * INTO build_row FROM plm.rag_embedding_builds
     WHERE embedding_build_id=NEW.embedding_build_id FOR KEY SHARE;
    IF TG_OP='INSERT' THEN
        IF build_row.embedding_build_id IS NULL OR build_row.build_state<>'PLANNED'
           OR build_row.created_xid<>txid_current() OR NEW.created_xid<>build_row.created_xid
           OR NEW.batch_state<>'PENDING' OR NEW.lock_version<>0 OR NEW.send_fencing_token IS NOT NULL
           OR NEW.provider_request_ref IS NOT NULL OR NEW.error_code IS NOT NULL
           OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL THEN
            RAISE EXCEPTION 'RAG EmbeddingBuildBatch initial state is invalid'; END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO job_row FROM plm.job_jobs
     WHERE job_id=build_row.build_job_ref FOR KEY SHARE;
    SELECT * INTO lease_row FROM plm.job_leases
     WHERE job_id=build_row.build_job_ref AND fencing_token=1 FOR KEY SHARE;
    SELECT * INTO attempt_row FROM plm.job_attempts
     WHERE job_id=build_row.build_job_ref AND fencing_token=1 FOR KEY SHARE;
    now_at_db := clock_timestamp();

    IF OLD.batch_state='PENDING' AND NEW.batch_state='RUNNING' THEN
        SELECT * INTO authz_row FROM plm.ai_egress_authorizations
         WHERE authorization_id=NEW.egress_authorization_ref FOR SHARE;
        SELECT * INTO model_row FROM plm.ai_models
         WHERE ai_model_id=build_row.embedding_model_ref FOR SHARE;
        SELECT * INTO provider_row FROM plm.ai_providers
         WHERE ai_provider_id=authz_row.ai_provider_id FOR SHARE;
        SELECT * INTO config_row FROM plm.ai_provider_config_versions
         WHERE provider_config_version_id=authz_row.provider_config_version_id
           AND ai_provider_id=authz_row.ai_provider_id FOR SHARE;
        PERFORM 1 FROM plm.rag_index_source_chunks source
          JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
         WHERE source.embedding_index_id=build_row.embedding_index_id
           AND source.source_ordinal BETWEEN NEW.source_first_ordinal
               AND NEW.source_first_ordinal+NEW.source_record_count-1
         FOR SHARE OF source,chunk;
        SELECT count(*),bool_and(
                   chunk.chunk_state='ACTIVE'
                   AND ROW(source.scope,source.project_id)
                       IS NOT DISTINCT FROM ROW(build_row.scope,build_row.project_id)
                   AND ROW(chunk.scope,chunk.project_id)
                       IS NOT DISTINCT FROM ROW(build_row.scope,build_row.project_id)
                   AND source.chunk_text_fingerprint=chunk.text_fingerprint
                   AND authz_row.allowed_data_categories ? chunk.source_type),
               sha256(convert_to(string_agg(
                   source.source_ordinal::text || ':' || source.chunk_id::text || ':' ||
                   encode(source.chunk_text_fingerprint,'hex'), E'\n'
                   ORDER BY source.source_ordinal), 'UTF8'))
          INTO source_count,source_is_current,current_source_fingerprint
          FROM plm.rag_index_source_chunks source
          JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
         WHERE source.embedding_index_id=build_row.embedding_index_id
           AND source.source_ordinal BETWEEN NEW.source_first_ordinal
               AND NEW.source_first_ordinal+NEW.source_record_count-1;
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_build_batch_id,NEW.embedding_build_id,NEW.batch_ordinal,
                  NEW.source_first_ordinal,NEW.source_record_count,NEW.source_batch_fingerprint,
                  NEW.payload_fingerprint,NEW.payload_bytes,NEW.input_tokens,
                  NEW.egress_authorization_ref,NEW.provider_request_ref,
                  NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_build_batch_id,OLD.embedding_build_id,OLD.batch_ordinal,
                  OLD.source_first_ordinal,OLD.source_record_count,OLD.source_batch_fingerprint,
                  OLD.payload_fingerprint,OLD.payload_bytes,OLD.input_tokens,
                  OLD.egress_authorization_ref,OLD.provider_request_ref,
                  OLD.created_at,OLD.created_xid)
           OR NEW.send_fencing_token<>1 OR NEW.error_code IS NOT NULL
           OR NEW.started_at IS NULL OR NEW.completed_at IS NOT NULL
           OR NEW.started_at<attempt_row.started_at OR NEW.started_at>now_at_db
           OR build_row.build_state<>'RUNNING' OR build_row.lock_version<>1
           OR job_row.state<>'RUNNING' OR job_row.max_attempts<>1
           OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
           OR job_row.completed_at IS NOT NULL OR job_row.lease_expires_at IS NULL
           OR job_row.lease_expires_at<=now_at_db
           OR lease_row.lease_id IS NULL OR lease_row.state<>'ACTIVE'
           OR lease_row.lease_expires_at<>job_row.lease_expires_at
           OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
           OR attempt_row.worker_ref<>lease_row.worker_ref
           OR attempt_row.completed_at IS NOT NULL OR attempt_row.error_code IS NOT NULL
           OR authz_row.authorization_id IS NULL OR authz_row.authorization_state<>'AUTHORIZED'
           OR authz_row.valid_until<=now_at_db
           OR ROW(authz_row.scope,authz_row.project_id)
              IS DISTINCT FROM ROW(build_row.scope,build_row.project_id)
           OR authz_row.operation_type NOT IN ('INDEX_BUILD','INDEX_REBUILD')
           OR authz_row.ai_model_id<>build_row.embedding_model_ref
           OR authz_row.max_retry_attempts<>1
           OR authz_row.max_record_count<NEW.source_record_count
           OR authz_row.max_payload_bytes<NEW.payload_bytes
           OR authz_row.max_input_tokens<NEW.input_tokens
           OR authz_row.payload_fingerprint<>NEW.payload_fingerprint
           OR authz_row.source_refs_fingerprint<>NEW.source_batch_fingerprint
           OR model_row.ai_model_id IS NULL OR model_row.model_kind<>'EMBEDDING'
           OR model_row.embedding_dimension<>build_row.embedding_dimension
           OR model_row.model_state<>'AVAILABLE'
           OR model_row.ai_provider_id<>authz_row.ai_provider_id
           OR provider_row.ai_provider_id IS NULL OR provider_row.provider_state<>'ACTIVE'
           OR provider_row.current_config_version_ref<>authz_row.provider_config_version_id
           OR config_row.provider_config_version_id IS NULL OR config_row.can_embedding IS DISTINCT FROM true
           OR config_row.data_region<>authz_row.data_region
           OR source_count<>NEW.source_record_count
           OR source_is_current IS DISTINCT FROM true
           OR current_source_fingerprint IS DISTINCT FROM NEW.source_batch_fingerprint THEN
            RAISE EXCEPTION 'RAG EmbeddingBuildBatch send fence proof is invalid';
        END IF;
        RETURN NEW;
    END IF;

    IF build_row.build_state<>'RUNNING' OR build_row.lock_version<>1
       OR job_row.state<>'FAILED' OR job_row.completed_at IS NULL
       OR job_row.lease_expires_at IS NOT NULL OR lease_row.state<>'EXPIRED'
       OR attempt_row.completed_at<>job_row.completed_at
       OR attempt_row.error_code NOT IN ('RAG_BUILD_LEASE_EXPIRED','RAG_PROVIDER_OUTCOME_UNKNOWN')
       OR NEW.lock_version<>OLD.lock_version+1
       OR ROW(NEW.embedding_build_batch_id,NEW.embedding_build_id,NEW.batch_ordinal,
              NEW.source_first_ordinal,NEW.source_record_count,NEW.source_batch_fingerprint,
              NEW.payload_fingerprint,NEW.payload_bytes,NEW.input_tokens,
              NEW.egress_authorization_ref,NEW.send_fencing_token,NEW.provider_request_ref,
              NEW.created_at,NEW.created_xid)
          IS DISTINCT FROM
          ROW(OLD.embedding_build_batch_id,OLD.embedding_build_id,OLD.batch_ordinal,
              OLD.source_first_ordinal,OLD.source_record_count,OLD.source_batch_fingerprint,
              OLD.payload_fingerprint,OLD.payload_bytes,OLD.input_tokens,
              OLD.egress_authorization_ref,OLD.send_fencing_token,OLD.provider_request_ref,
              OLD.created_at,OLD.created_xid) THEN
        RAISE EXCEPTION 'RAG EmbeddingBuildBatch reconciliation proof is invalid';
    END IF;
    IF OLD.batch_state='PENDING' THEN
        IF NEW.batch_state<>'CANCELLED' OR NEW.error_code<>'RAG_BUILD_LEASE_EXPIRED'
           OR NEW.started_at IS NULL OR NEW.completed_at<>NEW.started_at THEN
            RAISE EXCEPTION 'RAG pending Batch cancellation is invalid'; END IF;
    ELSIF OLD.batch_state='RUNNING' THEN
        IF NEW.batch_state<>'UNKNOWN' OR NEW.error_code<>'RAG_PROVIDER_OUTCOME_UNKNOWN'
           OR NEW.started_at<>OLD.started_at OR NEW.completed_at IS NULL
           OR NEW.completed_at<NEW.started_at THEN
            RAISE EXCEPTION 'RAG running Batch unknown transition is invalid'; END IF;
    ELSE
        RAISE EXCEPTION 'RAG terminal EmbeddingBuildBatch history is retained';
    END IF;
    RETURN NEW;
END; $$;
"""


def _previous_batch_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0081_rag_embedding_build_reconciliation"
    )
    start = previous._GUARDS.index(
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build_batch()"
    )
    end = previous._GUARDS.index(
        "CREATE FUNCTION plm.validate_rag_embedding_build_failed()", start,
    )
    return previous._GUARDS[start:end]


def upgrade() -> None:
    op.execute(_BATCH_GUARD)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG EmbeddingBuildBatch send-fence downgrade is disabled")
    op.execute("LOCK TABLE plm.rag_embedding_build_batches IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches
                        WHERE send_fencing_token IS NOT NULL) THEN
                RAISE EXCEPTION 'fenced RAG EmbeddingBuildBatch history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute(_previous_batch_guard())
