"""Allow validated RAG build completion and READY convergence.

Revision ID: 20261004_0086
Revises: 20261004_0085
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0086"
down_revision = "20261004_0085"
branch_labels = None
depends_on = None


_BUILD_SUCCESS = r"""
    IF TG_OP='UPDATE' AND OLD.build_state='RUNNING'
       AND NEW.build_state='SUCCEEDED' THEN
        SELECT * INTO lease_row FROM plm.job_leases
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        SELECT * INTO attempt_row FROM plm.job_attempts
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
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
           OR job_row.state<>'SUCCEEDED' OR job_row.max_attempts<>1
           OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
           OR job_row.lease_expires_at IS NOT NULL
           OR job_row.completed_at IS NULL
           OR job_row.payload_refs<>expected_payload
           OR lease_row.lease_id IS NULL OR lease_row.state<>'RELEASED'
           OR lease_row.lease_expires_at<=job_row.completed_at
           OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
           OR attempt_row.completed_at<>job_row.completed_at
           OR attempt_row.error_code IS NOT NULL
           OR attempt_row.worker_ref<>lease_row.worker_ref
           OR NOT EXISTS (
                SELECT 1 FROM plm.rag_embedding_index_validations validation
                 WHERE validation.embedding_index_id=NEW.embedding_index_id
                   AND validation.embedding_build_id=NEW.embedding_build_id
                   AND validation.validation_state='PASSED'
                   AND validation.completed_at<=job_row.completed_at)
           OR EXISTS (
                SELECT 1 FROM plm.rag_embedding_build_batches batch
                 WHERE batch.embedding_build_id=NEW.embedding_build_id
                   AND batch.batch_state<>'SUCCEEDED') THEN
            RAISE EXCEPTION 'RAG EmbeddingBuild validated success proof is invalid';
        END IF;
        RETURN NEW;
    END IF;

"""


_BUILD_VALIDATION_FAILURE = r"""
    IF TG_OP='UPDATE' AND OLD.build_state='RUNNING'
       AND NEW.build_state='FAILED' THEN
        SELECT * INTO lease_row FROM plm.job_leases
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        SELECT * INTO attempt_row FROM plm.job_attempts
         WHERE job_id=NEW.build_job_ref AND fencing_token=1 FOR KEY SHARE;
        IF lease_row.state='RELEASED'
           AND attempt_row.error_code=
               'RAG_INDEX_TECHNICAL_VALIDATION_FAILED' THEN
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
               OR lease_row.lease_expires_at<=job_row.completed_at
               OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
               OR attempt_row.completed_at<>job_row.completed_at
               OR attempt_row.worker_ref<>lease_row.worker_ref
               OR NOT EXISTS (
                    SELECT 1 FROM plm.rag_embedding_index_validations validation
                     WHERE validation.embedding_index_id=NEW.embedding_index_id
                       AND validation.embedding_build_id=NEW.embedding_build_id
                       AND validation.validation_state='FAILED'
                       AND validation.error_code=
                         'RAG_INDEX_TECHNICAL_VALIDATION_FAILED'
                       AND validation.completed_at<=job_row.completed_at)
               OR EXISTS (
                    SELECT 1 FROM plm.rag_embedding_build_batches batch
                     WHERE batch.embedding_build_id=NEW.embedding_build_id
                       AND batch.batch_state<>'SUCCEEDED') THEN
                RAISE EXCEPTION
                    'RAG EmbeddingBuild technical validation failure is invalid';
            END IF;
            RETURN NEW;
        END IF;
    END IF;

"""


_INDEX_SUCCESS = r"""
    IF OLD.index_state='BUILDING' AND NEW.index_state='READY' THEN
        SELECT * INTO job_row FROM plm.job_jobs
         WHERE job_id=build_row.build_job_ref FOR KEY SHARE;
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_index_id,NEW.scope,NEW.project_id,
                  NEW.index_purpose,NEW.embedding_model_ref,
                  NEW.embedding_dimension,NEW.chunk_profile,
                  NEW.chunk_profile_version,NEW.source_chunk_count,
                  NEW.source_snapshot_fingerprint,NEW.index_version,
                  NEW.created_by,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_index_id,OLD.scope,OLD.project_id,
                  OLD.index_purpose,OLD.embedding_model_ref,
                  OLD.embedding_dimension,OLD.chunk_profile,
                  OLD.chunk_profile_version,OLD.source_chunk_count,
                  OLD.source_snapshot_fingerprint,OLD.index_version,
                  OLD.created_by,OLD.created_at,OLD.created_xid)
           OR build_row.build_state<>'SUCCEEDED'
           OR build_row.lock_version<>2
           OR job_row.state<>'SUCCEEDED'
           OR job_row.completed_at IS NULL
           OR job_row.lease_expires_at IS NOT NULL
           OR NOT EXISTS (
                SELECT 1 FROM plm.rag_embedding_index_validations validation
                 WHERE validation.embedding_index_id=NEW.embedding_index_id
                   AND validation.embedding_build_id=build_row.embedding_build_id
                   AND validation.validation_state='PASSED'
                   AND validation.completed_at<=job_row.completed_at) THEN
            RAISE EXCEPTION 'RAG EmbeddingIndex READY proof is invalid';
        END IF;
        RETURN NEW;
    END IF;

"""


_SUCCESS_VALIDATORS = r"""
CREATE FUNCTION plm.validate_rag_embedding_success_transaction()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    job_row plm.job_jobs%ROWTYPE;
    build_row plm.rag_embedding_builds%ROWTYPE;
    index_row plm.rag_embedding_indexes%ROWTYPE;
    lease_row plm.job_leases%ROWTYPE;
    attempt_row plm.job_attempts%ROWTYPE;
    validation_row plm.rag_embedding_index_validations%ROWTYPE;
BEGIN
    IF TG_TABLE_NAME='job_jobs' THEN
        IF NEW.owner_module<>'rag' OR NEW.job_type<>'RAG_INDEX_BUILD'
           OR NEW.state<>'SUCCEEDED' THEN RETURN NULL; END IF;
        SELECT * INTO job_row FROM plm.job_jobs
         WHERE job_id=NEW.job_id;
        SELECT * INTO build_row FROM plm.rag_embedding_builds
         WHERE build_job_ref=NEW.job_id;
    ELSE
        IF NEW.build_state<>'SUCCEEDED' THEN RETURN NULL; END IF;
        SELECT * INTO build_row FROM plm.rag_embedding_builds
         WHERE embedding_build_id=NEW.embedding_build_id;
        SELECT * INTO job_row FROM plm.job_jobs
         WHERE job_id=build_row.build_job_ref;
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=build_row.embedding_index_id;
    SELECT * INTO validation_row FROM plm.rag_embedding_index_validations
     WHERE embedding_build_id=build_row.embedding_build_id;
    SELECT * INTO lease_row FROM plm.job_leases
     WHERE job_id=job_row.job_id AND fencing_token=1;
    SELECT * INTO attempt_row FROM plm.job_attempts
     WHERE job_id=job_row.job_id AND fencing_token=1;
    IF build_row.embedding_build_id IS NULL
       OR build_row.build_state<>'SUCCEEDED' OR build_row.lock_version<>2
       OR index_row.embedding_index_id IS NULL
       OR index_row.index_state<>'READY' OR index_row.lock_version<>2
       OR job_row.state<>'SUCCEEDED' OR job_row.max_attempts<>1
       OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
       OR job_row.lease_expires_at IS NOT NULL OR job_row.completed_at IS NULL
       OR lease_row.lease_id IS NULL OR lease_row.state<>'RELEASED'
       OR lease_row.lease_expires_at<=job_row.completed_at
       OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
       OR attempt_row.completed_at<>job_row.completed_at
       OR attempt_row.error_code IS NOT NULL
       OR attempt_row.worker_ref<>lease_row.worker_ref
       OR validation_row.embedding_index_validation_id IS NULL
       OR validation_row.embedding_index_id<>index_row.embedding_index_id
       OR validation_row.validation_state<>'PASSED'
       OR validation_row.completed_at>job_row.completed_at
       OR EXISTS (
            SELECT 1 FROM plm.rag_embedding_build_batches batch
             WHERE batch.embedding_build_id=build_row.embedding_build_id
               AND batch.batch_state<>'SUCCEEDED') THEN
        RAISE EXCEPTION
            'RAG Embedding validated success transaction is incomplete';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_embedding_build_success
AFTER UPDATE ON plm.rag_embedding_builds
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_rag_embedding_success_transaction();

CREATE CONSTRAINT TRIGGER trg_rag_embedding_job_success
AFTER UPDATE ON plm.job_jobs
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_rag_embedding_success_transaction();
"""


def _function(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def _build_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0084_rag_embedding_batch_failure"
    )
    source = previous._build_guard()
    marker = (
        "    IF TG_OP='UPDATE' AND OLD.build_state='RUNNING' "
        "AND NEW.build_state='FAILED' THEN"
    )
    if source.count(marker) != 1:
        raise RuntimeError("Schema0084 Build guard shape changed")
    return source.replace(
        marker, _BUILD_SUCCESS + _BUILD_VALIDATION_FAILURE + marker,
    )


def _index_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0081_rag_embedding_build_reconciliation"
    )
    source = _function(
        previous._GUARDS,
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_index()",
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build_batch()",
    )
    marker = "    IF OLD.index_state='BUILDING' AND NEW.index_state='FAILED' THEN"
    if source.count(marker) != 1:
        raise RuntimeError("Schema0081 Index guard shape changed")
    return source.replace(marker, _INDEX_SUCCESS + marker)


def _previous_index_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0081_rag_embedding_build_reconciliation"
    )
    return _function(
        previous._GUARDS,
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_index()",
        "CREATE OR REPLACE FUNCTION plm.guard_rag_embedding_build_batch()",
    )


def upgrade() -> None:
    op.execute(_build_guard())
    op.execute(_index_guard())
    op.execute(_SUCCESS_VALIDATORS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Embedding READY downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.job_jobs, plm.rag_embedding_builds, "
        "plm.rag_embedding_indexes IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_builds
                        WHERE build_state='SUCCEEDED')
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_indexes
                           WHERE index_state='READY')
               OR EXISTS (SELECT 1 FROM plm.job_jobs
                           WHERE owner_module='rag'
                             AND job_type='RAG_INDEX_BUILD'
                             AND state='SUCCEEDED')
               OR EXISTS (SELECT 1 FROM plm.job_attempts
                           WHERE error_code=
                             'RAG_INDEX_TECHNICAL_VALIDATION_FAILED') THEN
                RAISE EXCEPTION 'validated RAG READY history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_embedding_job_success ON plm.job_jobs")
    op.execute(
        "DROP TRIGGER trg_rag_embedding_build_success "
        "ON plm.rag_embedding_builds"
    )
    op.execute("DROP FUNCTION plm.validate_rag_embedding_success_transaction()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261004_0084_rag_embedding_batch_failure"
    )
    op.execute(previous._build_guard())
    op.execute(_previous_index_guard())
