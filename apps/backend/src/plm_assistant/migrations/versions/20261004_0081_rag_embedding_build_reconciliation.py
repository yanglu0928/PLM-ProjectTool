"""Add atomic expired RAG build reconciliation.

Revision ID: 20261004_0081
Revises: 20261004_0080
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0081"
down_revision = "20261004_0080"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
    lease_row plm.job_leases%ROWTYPE;
    attempt_row plm.job_attempts%ROWTYPE;
    expected_payload jsonb;
    now_at_db timestamptz;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'RAG EmbeddingBuild history is retained'; END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO job_row FROM plm.job_jobs
     WHERE job_id=NEW.build_job_ref FOR KEY SHARE;
    expected_payload := jsonb_build_object(
        'embedding_build_id',NEW.embedding_build_id::text,
        'embedding_index_id',NEW.embedding_index_id::text,
        'build_generation',NEW.build_generation);
    IF TG_OP='UPDATE' AND OLD.build_state='RUNNING' AND NEW.build_state='FAILED' THEN
        SELECT * INTO lease_row FROM plm.job_leases
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        SELECT * INTO attempt_row FROM plm.job_attempts
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_build_id,NEW.embedding_index_id,NEW.scope,NEW.project_id,
                  NEW.embedding_model_ref,NEW.embedding_dimension,NEW.build_generation,
                  NEW.build_job_ref,NEW.source_chunk_count,NEW.source_snapshot_fingerprint,
                  NEW.batch_count,NEW.authorization_set_fingerprint,NEW.build_fingerprint,
                  NEW.created_by,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_build_id,OLD.embedding_index_id,OLD.scope,OLD.project_id,
                  OLD.embedding_model_ref,OLD.embedding_dimension,OLD.build_generation,
                  OLD.build_job_ref,OLD.source_chunk_count,OLD.source_snapshot_fingerprint,
                  OLD.batch_count,OLD.authorization_set_fingerprint,OLD.build_fingerprint,
                  OLD.created_by,OLD.created_at,OLD.created_xid)
           OR index_row.index_state<>'BUILDING' OR index_row.lock_version<>1
           OR job_row.state<>'FAILED' OR job_row.max_attempts<>1
           OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
           OR job_row.lease_expires_at IS NOT NULL OR job_row.completed_at IS NULL
           OR job_row.payload_refs<>expected_payload
           OR lease_row.lease_id IS NULL OR lease_row.state<>'EXPIRED'
           OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
           OR attempt_row.completed_at<>job_row.completed_at
           OR attempt_row.error_code NOT IN
              ('RAG_BUILD_LEASE_EXPIRED','RAG_PROVIDER_OUTCOME_UNKNOWN')
           OR attempt_row.worker_ref<>lease_row.worker_ref
           OR lease_row.lease_expires_at>job_row.completed_at
           OR EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches batch
                       WHERE batch.embedding_build_id=NEW.embedding_build_id
                         AND batch.batch_state IN ('PENDING','RUNNING')) THEN
            RAISE EXCEPTION 'RAG EmbeddingBuild expired reconciliation is invalid';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP='INSERT' THEN
        IF index_row.embedding_index_id IS NULL OR index_row.index_state<>'PLANNED'
           OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM ROW(index_row.scope,index_row.project_id)
           OR NEW.embedding_model_ref<>index_row.embedding_model_ref
           OR NEW.embedding_dimension<>index_row.embedding_dimension
           OR NEW.source_chunk_count<>index_row.source_chunk_count
           OR NEW.source_snapshot_fingerprint<>index_row.source_snapshot_fingerprint
           OR NEW.build_generation<>1 OR NEW.build_state<>'PLANNED'
           OR NEW.lock_version<>0 OR NEW.created_xid<>txid_current() THEN
            RAISE EXCEPTION 'RAG EmbeddingBuild Index binding or initial state is invalid';
        END IF;
        IF job_row.job_id IS NULL OR job_row.owner_module<>'rag'
           OR job_row.job_type<>'RAG_INDEX_BUILD'
           OR ROW(job_row.scope,job_row.project_id) IS DISTINCT FROM ROW(NEW.scope,NEW.project_id)
           OR job_row.actor_ref IS DISTINCT FROM NEW.created_by
           OR job_row.payload_refs<>expected_payload OR job_row.state<>'PENDING'
           OR job_row.max_attempts<>1 OR job_row.attempt_count<>0 OR job_row.fencing_token<>0 THEN
            RAISE EXCEPTION 'RAG EmbeddingBuild unique Job Owner binding is invalid';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.build_state<>'PLANNED' OR NEW.build_state<>'RUNNING'
       OR NEW.lock_version<>OLD.lock_version+1
       OR ROW(NEW.embedding_build_id,NEW.embedding_index_id,NEW.scope,NEW.project_id,
              NEW.embedding_model_ref,NEW.embedding_dimension,NEW.build_generation,
              NEW.build_job_ref,NEW.source_chunk_count,NEW.source_snapshot_fingerprint,
              NEW.batch_count,NEW.authorization_set_fingerprint,NEW.build_fingerprint,
              NEW.created_by,NEW.created_at,NEW.created_xid)
          IS DISTINCT FROM
          ROW(OLD.embedding_build_id,OLD.embedding_index_id,OLD.scope,OLD.project_id,
              OLD.embedding_model_ref,OLD.embedding_dimension,OLD.build_generation,
              OLD.build_job_ref,OLD.source_chunk_count,OLD.source_snapshot_fingerprint,
              OLD.batch_count,OLD.authorization_set_fingerprint,OLD.build_fingerprint,
              OLD.created_by,OLD.created_at,OLD.created_xid)
       OR index_row.index_state<>'PLANNED' OR index_row.lock_version<>0
       OR job_row.owner_module<>'rag' OR job_row.job_type<>'RAG_INDEX_BUILD'
       OR job_row.state<>'RUNNING' OR job_row.max_attempts<>1
       OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
       OR job_row.completed_at IS NOT NULL OR job_row.payload_refs<>expected_payload
       OR ROW(job_row.scope,job_row.project_id,job_row.actor_ref)
          IS DISTINCT FROM ROW(NEW.scope,NEW.project_id,NEW.created_by) THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild leased start is invalid';
    END IF;
    now_at_db := clock_timestamp();
    SELECT * INTO lease_row FROM plm.job_leases
     WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
    SELECT * INTO attempt_row FROM plm.job_attempts
     WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
    IF job_row.lease_expires_at IS NULL OR job_row.lease_expires_at<=now_at_db
       OR lease_row.lease_id IS NULL OR lease_row.state<>'ACTIVE'
       OR lease_row.lease_expires_at<>job_row.lease_expires_at
       OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
       OR attempt_row.worker_ref<>lease_row.worker_ref
       OR attempt_row.completed_at IS NOT NULL OR attempt_row.error_code IS NOT NULL
       OR EXISTS (SELECT 1 FROM plm.ai_models model WHERE model.ai_model_id=NEW.embedding_model_ref
                  AND (model.model_kind<>'EMBEDDING' OR model.embedding_dimension<>NEW.embedding_dimension
                       OR model.model_state<>'AVAILABLE'))
       OR NOT EXISTS (SELECT 1 FROM plm.ai_models model WHERE model.ai_model_id=NEW.embedding_model_ref)
       OR EXISTS (SELECT 1 FROM plm.rag_index_source_chunks source
                  JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
                  WHERE source.embedding_index_id=NEW.embedding_index_id AND chunk.chunk_state<>'ACTIVE')
       OR EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches batch
                  JOIN plm.ai_egress_authorizations authz ON authz.authorization_id=batch.egress_authorization_ref
                  WHERE batch.embedding_build_id=NEW.embedding_build_id
                    AND (batch.batch_state<>'PENDING' OR batch.lock_version<>0
                         OR authz.authorization_state<>'AUTHORIZED' OR authz.valid_until<=now_at_db)) THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild current lease, model, source or authorization is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_index()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    model_kind text; model_dimension integer; model_state text;
    build_row plm.rag_embedding_builds%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'RAG EmbeddingIndex history is retained'; END IF;
    SELECT model.model_kind,model.embedding_dimension,model.model_state
      INTO model_kind,model_dimension,model_state FROM plm.ai_models model
     WHERE model.ai_model_id=NEW.embedding_model_ref FOR KEY SHARE;
    IF TG_OP='INSERT' THEN
        IF NEW.index_state<>'PLANNED' OR NEW.lock_version<>0 OR NEW.created_xid<>txid_current() THEN
            RAISE EXCEPTION 'RAG EmbeddingIndex must start PLANNED in its creation transaction'; END IF;
        IF model_kind IS DISTINCT FROM 'EMBEDDING' OR model_dimension IS DISTINCT FROM NEW.embedding_dimension
           OR model_state IS DISTINCT FROM 'AVAILABLE' THEN
            RAISE EXCEPTION 'RAG EmbeddingIndex model binding is invalid'; END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO build_row FROM plm.rag_embedding_builds
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    IF OLD.index_state='BUILDING' AND NEW.index_state='FAILED' THEN
        SELECT * INTO job_row FROM plm.job_jobs WHERE job_id=build_row.build_job_ref FOR KEY SHARE;
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_index_id,NEW.scope,NEW.project_id,NEW.index_purpose,
                  NEW.embedding_model_ref,NEW.embedding_dimension,NEW.chunk_profile,
                  NEW.chunk_profile_version,NEW.source_chunk_count,NEW.source_snapshot_fingerprint,
                  NEW.index_version,NEW.created_by,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_index_id,OLD.scope,OLD.project_id,OLD.index_purpose,
                  OLD.embedding_model_ref,OLD.embedding_dimension,OLD.chunk_profile,
                  OLD.chunk_profile_version,OLD.source_chunk_count,OLD.source_snapshot_fingerprint,
                  OLD.index_version,OLD.created_by,OLD.created_at,OLD.created_xid)
           OR build_row.build_state<>'FAILED' OR build_row.lock_version<>2
           OR job_row.state<>'FAILED' OR job_row.completed_at IS NULL
           OR job_row.attempt_count<>1 OR job_row.fencing_token<>1 THEN
            RAISE EXCEPTION 'RAG EmbeddingIndex expired failure transition is invalid';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.index_state<>'PLANNED' OR NEW.index_state<>'BUILDING'
       OR NEW.lock_version<>OLD.lock_version+1
       OR ROW(NEW.embedding_index_id,NEW.scope,NEW.project_id,NEW.index_purpose,
              NEW.embedding_model_ref,NEW.embedding_dimension,NEW.chunk_profile,
              NEW.chunk_profile_version,NEW.source_chunk_count,NEW.source_snapshot_fingerprint,
              NEW.index_version,NEW.created_by,NEW.created_at,NEW.created_xid)
          IS DISTINCT FROM
          ROW(OLD.embedding_index_id,OLD.scope,OLD.project_id,OLD.index_purpose,
              OLD.embedding_model_ref,OLD.embedding_dimension,OLD.chunk_profile,
              OLD.chunk_profile_version,OLD.source_chunk_count,OLD.source_snapshot_fingerprint,
              OLD.index_version,OLD.created_by,OLD.created_at,OLD.created_xid)
       OR model_kind IS DISTINCT FROM 'EMBEDDING' OR model_dimension IS DISTINCT FROM NEW.embedding_dimension
       OR model_state IS DISTINCT FROM 'AVAILABLE' OR build_row.embedding_build_id IS NULL
       OR build_row.build_state<>'RUNNING' OR build_row.lock_version<>1
       OR ROW(build_row.scope,build_row.project_id,build_row.embedding_model_ref,
              build_row.embedding_dimension,build_row.source_chunk_count,build_row.source_snapshot_fingerprint)
          IS DISTINCT FROM ROW(NEW.scope,NEW.project_id,NEW.embedding_model_ref,
              NEW.embedding_dimension,NEW.source_chunk_count,NEW.source_snapshot_fingerprint) THEN
        RAISE EXCEPTION 'RAG EmbeddingIndex leased BUILDING transition is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build_batch()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    build_row plm.rag_embedding_builds%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
    lease_row plm.job_leases%ROWTYPE;
    attempt_row plm.job_attempts%ROWTYPE;
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
    SELECT * INTO job_row FROM plm.job_jobs WHERE job_id=build_row.build_job_ref FOR KEY SHARE;
    SELECT * INTO lease_row FROM plm.job_leases
     WHERE job_id=build_row.build_job_ref AND fencing_token=1 FOR KEY SHARE;
    SELECT * INTO attempt_row FROM plm.job_attempts
     WHERE job_id=build_row.build_job_ref AND fencing_token=1 FOR KEY SHARE;
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

CREATE FUNCTION plm.validate_rag_embedding_build_failed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
BEGIN
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id;
    SELECT * INTO job_row FROM plm.job_jobs WHERE job_id=NEW.build_job_ref;
    IF NEW.build_state='FAILED' AND (
       index_row.index_state<>'FAILED' OR index_row.lock_version<>2
       OR job_row.state<>'FAILED' OR job_row.completed_at IS NULL
       OR job_row.lease_expires_at IS NOT NULL
       OR EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches batch
                  WHERE batch.embedding_build_id=NEW.embedding_build_id
                    AND batch.batch_state IN ('PENDING','RUNNING'))) THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild failed reconciliation transaction is incomplete';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_embedding_build_failed
AFTER UPDATE ON plm.rag_embedding_builds
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_rag_embedding_build_failed();
"""


def upgrade() -> None:
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG EmbeddingBuild reconciliation downgrade is disabled")
    op.execute("LOCK TABLE plm.rag_embedding_build_batches, plm.rag_embedding_builds, "
               "plm.rag_embedding_indexes IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_builds WHERE build_state='FAILED')
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_indexes WHERE index_state='FAILED')
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches
                           WHERE error_code IN ('RAG_BUILD_LEASE_EXPIRED',
                                                'RAG_PROVIDER_OUTCOME_UNKNOWN')) THEN
                RAISE EXCEPTION 'reconciled RAG EmbeddingBuild history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_embedding_build_failed ON plm.rag_embedding_builds")
    op.execute("DROP FUNCTION plm.validate_rag_embedding_build_failed()")
    op.execute("DROP TRIGGER trg_rag_embedding_build_started ON plm.rag_embedding_builds")
    op.execute("DROP FUNCTION plm.validate_rag_embedding_build_started()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0080_rag_embedding_build_begin"
    )
    op.execute(previous._GUARDS)
