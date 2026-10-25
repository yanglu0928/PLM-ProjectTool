"""Allow atomic known Embedding failure terminalization.

Revision ID: 20261004_0084
Revises: 20261004_0083
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0084"
down_revision = "20261004_0083"
branch_labels = None
depends_on = None


_ACTIVE_BUILD_FAILURE = r"""
    IF TG_OP='UPDATE' AND OLD.build_state='RUNNING'
       AND NEW.build_state='FAILED' THEN
        SELECT * INTO lease_row FROM plm.job_leases
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        SELECT * INTO attempt_row FROM plm.job_attempts
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        IF lease_row.state='RELEASED'
           AND attempt_row.error_code IN
              ('RAG_PROVIDER_REQUEST_REJECTED','RAG_EMBEDDING_RESPONSE_INVALID') THEN
            IF NEW.lock_version<>OLD.lock_version+1
               OR ROW(NEW.embedding_build_id,NEW.embedding_index_id,
                      NEW.scope,NEW.project_id,NEW.embedding_model_ref,
                      NEW.embedding_dimension,NEW.build_generation,
                      NEW.build_job_ref,NEW.source_chunk_count,
                      NEW.source_snapshot_fingerprint,NEW.batch_count,
                      NEW.authorization_set_fingerprint,NEW.build_fingerprint,
                      NEW.created_by,NEW.created_at,NEW.created_xid)
                  IS DISTINCT FROM
                  ROW(OLD.embedding_build_id,OLD.embedding_index_id,
                      OLD.scope,OLD.project_id,OLD.embedding_model_ref,
                      OLD.embedding_dimension,OLD.build_generation,
                      OLD.build_job_ref,OLD.source_chunk_count,
                      OLD.source_snapshot_fingerprint,OLD.batch_count,
                      OLD.authorization_set_fingerprint,OLD.build_fingerprint,
                      OLD.created_by,OLD.created_at,OLD.created_xid)
               OR index_row.index_state<>'BUILDING'
               OR index_row.lock_version<>1
               OR job_row.state<>'FAILED' OR job_row.max_attempts<>1
               OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
               OR job_row.lease_expires_at IS NOT NULL
               OR job_row.completed_at IS NULL
               OR job_row.payload_refs<>expected_payload
               OR lease_row.lease_id IS NULL
               OR lease_row.lease_expires_at<job_row.completed_at
               OR attempt_row.attempt_id IS NULL
               OR attempt_row.attempt_no<>1
               OR attempt_row.completed_at<>job_row.completed_at
               OR attempt_row.worker_ref<>lease_row.worker_ref
               OR (SELECT count(*)
                     FROM plm.rag_embedding_build_batches batch
                    WHERE batch.embedding_build_id=NEW.embedding_build_id
                      AND batch.batch_state='FAILED'
                      AND batch.error_code=attempt_row.error_code)<>1
               OR EXISTS (
                    SELECT 1 FROM plm.rag_embedding_build_batches batch
                     WHERE batch.embedding_build_id=NEW.embedding_build_id
                       AND ((batch.batch_state='FAILED'
                             AND batch.error_code<>attempt_row.error_code)
                            OR (batch.batch_state='CANCELLED'
                                AND batch.error_code<>
                                  'RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE')))
               OR EXISTS (
                    SELECT 1 FROM plm.rag_embedding_build_batches batch
                     WHERE batch.embedding_build_id=NEW.embedding_build_id
                       AND batch.batch_state IN ('PENDING','RUNNING')) THEN
                RAISE EXCEPTION
                    'RAG EmbeddingBuild known failure proof is invalid';
            END IF;
            RETURN NEW;
        END IF;
    END IF;

"""


_ACTIVE_BATCH_FAILURE = r"""
    IF OLD.batch_state='RUNNING' AND NEW.batch_state='FAILED'
       AND lease_row.state='RELEASED'
       AND attempt_row.error_code IN
          ('RAG_PROVIDER_REQUEST_REJECTED','RAG_EMBEDDING_RESPONSE_INVALID') THEN
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
           OR NEW.error_code<>attempt_row.error_code
           OR NEW.completed_at IS NULL OR NEW.completed_at<NEW.started_at
           OR NEW.completed_at<>job_row.completed_at
           OR build_row.build_state<>'RUNNING' OR build_row.lock_version<>1
           OR job_row.state<>'FAILED' OR job_row.max_attempts<>1
           OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
           OR job_row.lease_expires_at IS NOT NULL
           OR job_row.completed_at IS NULL
           OR lease_row.lease_id IS NULL
           OR lease_row.lease_expires_at<job_row.completed_at
           OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
           OR attempt_row.completed_at<>job_row.completed_at
           OR attempt_row.worker_ref<>lease_row.worker_ref
           OR (NEW.error_code='RAG_PROVIDER_REQUEST_REJECTED'
               AND NEW.provider_request_ref IS NOT NULL)
           OR (NEW.error_code='RAG_EMBEDDING_RESPONSE_INVALID'
               AND (NEW.provider_request_ref IS NULL
                    OR NEW.provider_request_ref !~ '^sha256:[0-9a-f]{64}$')) THEN
            RAISE EXCEPTION
                'RAG EmbeddingBuildBatch known failure proof is invalid';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.batch_state='PENDING' AND NEW.batch_state='CANCELLED'
       AND NEW.error_code='RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE'
       AND lease_row.state='RELEASED'
       AND attempt_row.error_code IN
          ('RAG_PROVIDER_REQUEST_REJECTED','RAG_EMBEDDING_RESPONSE_INVALID') THEN
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_build_batch_id,NEW.embedding_build_id,
                  NEW.batch_ordinal,NEW.source_first_ordinal,
                  NEW.source_record_count,NEW.source_batch_fingerprint,
                  NEW.payload_fingerprint,NEW.payload_bytes,NEW.input_tokens,
                  NEW.egress_authorization_ref,NEW.send_fencing_token,
                  NEW.provider_request_ref,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_build_batch_id,OLD.embedding_build_id,
                  OLD.batch_ordinal,OLD.source_first_ordinal,
                  OLD.source_record_count,OLD.source_batch_fingerprint,
                  OLD.payload_fingerprint,OLD.payload_bytes,OLD.input_tokens,
                  OLD.egress_authorization_ref,OLD.send_fencing_token,
                  OLD.provider_request_ref,OLD.created_at,OLD.created_xid)
           OR NEW.started_at<>job_row.completed_at
           OR NEW.completed_at<>job_row.completed_at
           OR build_row.build_state<>'RUNNING' OR build_row.lock_version<>1
           OR job_row.state<>'FAILED' OR job_row.lease_expires_at IS NOT NULL
           OR job_row.completed_at IS NULL OR lease_row.lease_id IS NULL
           OR lease_row.lease_expires_at<job_row.completed_at
           OR attempt_row.attempt_id IS NULL
           OR attempt_row.completed_at<>job_row.completed_at
           OR attempt_row.worker_ref<>lease_row.worker_ref THEN
            RAISE EXCEPTION
                'RAG pending Batch known failure cancellation is invalid';
        END IF;
        RETURN NEW;
    END IF;

"""


def _function(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def _build_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0081_rag_embedding_build_reconciliation"
    )
    source = _function(
        previous._GUARDS,
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build()",
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_index()",
    )
    marker = (
        "    IF TG_OP='UPDATE' AND OLD.build_state='RUNNING' "
        "AND NEW.build_state='FAILED' THEN"
    )
    if source.count(marker) != 1:
        raise RuntimeError("Schema0081 Build guard shape changed")
    return source.replace(marker, _ACTIVE_BUILD_FAILURE + marker)


def _batch_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0083_rag_embedding_batch_success"
    )
    source = previous._batch_guard()
    marker = "    IF build_row.build_state<>'RUNNING' OR build_row.lock_version<>1"
    if source.count(marker) != 1:
        raise RuntimeError("Schema0083 Batch guard shape changed")
    return source.replace(marker, _ACTIVE_BATCH_FAILURE + marker)


def _previous_build_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0081_rag_embedding_build_reconciliation"
    )
    return _function(
        previous._GUARDS,
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build()",
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_index()",
    )


def upgrade() -> None:
    op.execute(_build_guard())
    op.execute(_batch_guard())


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Embedding failure downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.rag_embedding_build_batches, "
        "plm.rag_embedding_builds IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM plm.rag_embedding_build_batches
                 WHERE error_code IN (
                    'RAG_PROVIDER_REQUEST_REJECTED',
                    'RAG_EMBEDDING_RESPONSE_INVALID',
                    'RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE')) THEN
                RAISE EXCEPTION
                    'known RAG Embedding failure history prevents downgrade';
            END IF;
        END $$;
    """)
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0083_rag_embedding_batch_success"
    )
    op.execute(_previous_build_guard())
    op.execute(previous._batch_guard())
