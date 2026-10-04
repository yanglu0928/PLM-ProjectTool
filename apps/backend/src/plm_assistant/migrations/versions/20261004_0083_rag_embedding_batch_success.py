"""Allow atomic successful Embedding Batch and record publication.

Revision ID: 20261004_0083
Revises: 20261004_0082
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0083"
down_revision = "20261004_0082"
branch_labels = None
depends_on = None


_SUCCESS_BRANCH = r"""
    IF OLD.batch_state='RUNNING' AND NEW.batch_state='SUCCEEDED' THEN
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_build_batch_id,NEW.embedding_build_id,
                  NEW.batch_ordinal,NEW.source_first_ordinal,
                  NEW.source_record_count,NEW.source_batch_fingerprint,
                  NEW.payload_fingerprint,NEW.payload_bytes,NEW.input_tokens,
                  NEW.egress_authorization_ref,NEW.send_fencing_token,
                  NEW.started_at,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_build_batch_id,OLD.embedding_build_id,
                  OLD.batch_ordinal,OLD.source_first_ordinal,
                  OLD.source_record_count,OLD.source_batch_fingerprint,
                  OLD.payload_fingerprint,OLD.payload_bytes,OLD.input_tokens,
                  OLD.egress_authorization_ref,OLD.send_fencing_token,
                  OLD.started_at,OLD.created_at,OLD.created_xid)
           OR NEW.send_fencing_token<>1 OR NEW.error_code IS NOT NULL
           OR NEW.provider_request_ref IS NULL
           OR NEW.completed_at IS NULL OR NEW.completed_at<NEW.started_at
           OR NEW.completed_at>now_at_db
           OR build_row.build_state<>'RUNNING' OR build_row.lock_version<>1
           OR job_row.state<>'RUNNING' OR job_row.max_attempts<>1
           OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
           OR job_row.completed_at IS NOT NULL OR job_row.lease_expires_at IS NULL
           OR job_row.lease_expires_at<=now_at_db
           OR lease_row.lease_id IS NULL OR lease_row.state<>'ACTIVE'
           OR lease_row.lease_expires_at<>job_row.lease_expires_at
           OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
           OR attempt_row.worker_ref<>lease_row.worker_ref
           OR attempt_row.completed_at IS NOT NULL
           OR attempt_row.error_code IS NOT NULL THEN
            RAISE EXCEPTION 'RAG EmbeddingBuildBatch success proof is invalid';
        END IF;
        RETURN NEW;
    END IF;

"""


def _batch_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0082_rag_embedding_batch_send_fence"
    )
    marker = "    IF build_row.build_state<>'RUNNING' OR build_row.lock_version<>1"
    if previous._BATCH_GUARD.count(marker) != 1:
        raise RuntimeError("Schema0082 Batch guard shape changed")
    return previous._BATCH_GUARD.replace(marker, _SUCCESS_BRANCH + marker)


_RECORD_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_record()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    build_row plm.rag_embedding_builds%ROWTYPE;
    batch_row plm.rag_embedding_build_batches%ROWTYPE;
    authorization_row plm.ai_egress_authorizations%ROWTYPE;
    source_ordinal_value bigint;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG EmbeddingRecord history is retained';
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO build_row FROM plm.rag_embedding_builds
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT source_ordinal INTO source_ordinal_value
      FROM plm.rag_index_source_chunks
     WHERE embedding_index_id=NEW.embedding_index_id AND chunk_id=NEW.chunk_id;
    SELECT * INTO batch_row FROM plm.rag_embedding_build_batches
     WHERE embedding_build_id=build_row.embedding_build_id
       AND source_ordinal_value BETWEEN source_first_ordinal
           AND source_first_ordinal+source_record_count-1 FOR KEY SHARE;
    SELECT * INTO authorization_row FROM plm.ai_egress_authorizations
     WHERE authorization_id=NEW.egress_authorization_ref FOR KEY SHARE;
    IF index_row.embedding_index_id IS NULL OR index_row.index_state<>'BUILDING'
       OR build_row.embedding_build_id IS NULL OR build_row.build_state<>'RUNNING'
       OR batch_row.embedding_build_batch_id IS NULL
       OR batch_row.batch_state<>'SUCCEEDED'
       OR batch_row.egress_authorization_ref<>NEW.egress_authorization_ref
       OR batch_row.provider_request_ref IS NULL
       OR NEW.provider_request_ref<>batch_row.provider_request_ref
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id)
       OR NEW.embedding_model_ref<>index_row.embedding_model_ref
       OR NEW.embedding_dimension<>index_row.embedding_dimension
       OR NEW.embedding_state<>'AVAILABLE'
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG EmbeddingRecord lacks a successful authorized Build batch';
    END IF;
    IF authorization_row.authorization_id IS NULL
       OR ROW(authorization_row.scope,authorization_row.project_id)
          IS DISTINCT FROM ROW(NEW.scope,NEW.project_id)
       OR authorization_row.ai_model_id<>NEW.embedding_model_ref
       OR authorization_row.operation_type NOT IN ('INDEX_BUILD','INDEX_REBUILD') THEN
        RAISE EXCEPTION 'RAG EmbeddingRecord egress authorization binding is invalid';
    END IF;
    RETURN NEW;
END; $$;
"""


_SUCCESS_VALIDATOR = r"""
CREATE FUNCTION plm.validate_rag_embedding_batch_success()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    build_row plm.rag_embedding_builds%ROWTYPE;
    actual_count bigint;
    valid_count bigint;
BEGIN
    IF NEW.batch_state<>'SUCCEEDED' THEN RETURN NULL; END IF;
    SELECT * INTO build_row FROM plm.rag_embedding_builds
     WHERE embedding_build_id=NEW.embedding_build_id;
    SELECT count(*),count(*) FILTER (WHERE
               record.embedding_state='AVAILABLE'
               AND ROW(record.scope,record.project_id)
                   IS NOT DISTINCT FROM ROW(build_row.scope,build_row.project_id)
               AND record.embedding_model_ref=build_row.embedding_model_ref
               AND record.embedding_dimension=build_row.embedding_dimension
               AND record.egress_authorization_ref=NEW.egress_authorization_ref
               AND record.provider_request_ref=NEW.provider_request_ref
               AND record.chunk_text_fingerprint=source.chunk_text_fingerprint)
      INTO actual_count,valid_count
      FROM plm.rag_index_source_chunks source
      LEFT JOIN plm.rag_embedding_records record
        ON record.embedding_index_id=source.embedding_index_id
       AND record.chunk_id=source.chunk_id
       AND record.embedding_state='AVAILABLE'
     WHERE source.embedding_index_id=build_row.embedding_index_id
       AND source.source_ordinal BETWEEN NEW.source_first_ordinal
           AND NEW.source_first_ordinal+NEW.source_record_count-1;
    IF build_row.embedding_build_id IS NULL
       OR build_row.build_state<>'RUNNING'
       OR actual_count<>NEW.source_record_count
       OR valid_count<>NEW.source_record_count THEN
        RAISE EXCEPTION 'RAG successful Batch record publication is incomplete';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_embedding_batch_success
AFTER UPDATE ON plm.rag_embedding_build_batches
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_rag_embedding_batch_success();
"""


def _previous_record_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0080_rag_embedding_build_begin"
    )
    start = previous._GUARDS.index(
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_record()"
    )
    end = previous._GUARDS.index(
        "CREATE FUNCTION plm.validate_rag_embedding_build_started()", start,
    )
    return previous._GUARDS[start:end]


def upgrade() -> None:
    op.execute(_batch_guard())
    op.execute(_RECORD_GUARD)
    op.execute(_SUCCESS_VALIDATOR)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Embedding success downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.rag_embedding_records, "
        "plm.rag_embedding_build_batches IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches
                        WHERE batch_state IN ('SUCCEEDED','FAILED'))
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_records) THEN
                RAISE EXCEPTION 'successful RAG Embedding history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_embedding_batch_success ON plm.rag_embedding_build_batches")
    op.execute("DROP FUNCTION plm.validate_rag_embedding_batch_success()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0082_rag_embedding_batch_send_fence"
    )
    op.execute(previous._BATCH_GUARD)
    op.execute(_previous_record_guard())
