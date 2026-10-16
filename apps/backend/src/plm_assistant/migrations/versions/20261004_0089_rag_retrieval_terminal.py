"""Add atomic RAG Retrieval terminal publication boundary.

Revision ID: 20261004_0089
Revises: 20261004_0088
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0089"
down_revision = "20261004_0088"
branch_labels = None
depends_on = None


_RUN_STATE_CHECK = r"""
top_k BETWEEN 1 AND 100 AND
rerank_state IN ('PENDING','NOT_APPLICABLE') AND
egress_state IN ('PENDING','NOT_APPLICABLE') AND
jsonb_typeof(quality_flags)='array' AND NOT degraded AND created_xid>0 AND
isfinite(created_at) AND (
  (retrieval_state='RUNNING' AND rerank_state IN ('PENDING','NOT_APPLICABLE')
   AND egress_state IN ('PENDING','NOT_APPLICABLE') AND quality_flags='[]'::jsonb
   AND error_code IS NULL AND completed_at IS NULL AND lock_version=0)
  OR
  (retrieval_state='SUCCEEDED' AND rerank_state='NOT_APPLICABLE'
   AND egress_state='NOT_APPLICABLE'
   AND quality_flags IN ('[]'::jsonb,'["CANDIDATE_SHORTFALL"]'::jsonb)
   AND error_code IS NULL AND completed_at IS NOT NULL
   AND isfinite(completed_at) AND completed_at>=created_at AND lock_version=1)
  OR
  (retrieval_state='FAILED' AND rerank_state='NOT_APPLICABLE'
   AND egress_state='NOT_APPLICABLE' AND quality_flags='[]'::jsonb
   AND error_code IN ('RAG_NO_AUTHORIZED_CANDIDATES',
                      'RAG_RETRIEVAL_PREPARATION_UNAVAILABLE',
                      'RAG_RETRIEVAL_LEASE_EXPIRED')
   AND completed_at IS NOT NULL AND isfinite(completed_at)
   AND completed_at>=created_at AND lock_version=1)
)
"""


_RUN_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_rag_retrieval_run_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    project_state text;
    job_row plm.job_jobs%ROWTYPE;
    global_index plm.rag_embedding_indexes%ROWTYPE;
    project_index plm.rag_embedding_indexes%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'RAG RetrievalRun history is retained';
    END IF;
    IF NEW.scope='PROJECT' THEN
        SELECT state INTO project_state FROM plm.prj_projects
         WHERE project_id=NEW.project_id FOR KEY SHARE;
    END IF;
    SELECT * INTO job_row FROM plm.job_jobs
     WHERE job_id=NEW.job_id FOR KEY SHARE;
    IF NEW.global_index_ref IS NOT NULL THEN
        SELECT * INTO global_index FROM plm.rag_embedding_indexes
         WHERE embedding_index_id=NEW.global_index_ref FOR KEY SHARE;
    END IF;
    IF NEW.project_index_ref IS NOT NULL THEN
        SELECT * INTO project_index FROM plm.rag_embedding_indexes
         WHERE embedding_index_id=NEW.project_index_ref FOR KEY SHARE;
    END IF;
    IF TG_OP='INSERT' THEN
        IF (NEW.scope='PROJECT' AND project_state IS DISTINCT FROM 'ACTIVE')
           OR job_row.job_id IS NULL OR job_row.owner_module<>'rag'
           OR job_row.job_type<>'RAG_RETRIEVAL'
           OR job_row.state<>'PENDING' OR job_row.scope<>NEW.scope
           OR job_row.project_id IS DISTINCT FROM NEW.project_id
           OR job_row.actor_ref IS DISTINCT FROM NEW.actor_ref
           OR job_row.trace_id<>NEW.trace_id::text
           OR job_row.payload_refs<>jsonb_build_object(
                'retrieval_run_id',NEW.retrieval_run_id::text)
           OR (NEW.global_index_ref IS NOT NULL AND
               (global_index.embedding_index_id IS NULL
                OR global_index.scope<>'GLOBAL'
                OR global_index.project_id IS NOT NULL
                OR global_index.index_state<>'ACTIVE'))
           OR (NEW.scope='GLOBAL' AND
               (NEW.global_index_ref IS NULL OR NEW.project_index_ref IS NOT NULL))
           OR (NEW.scope='PROJECT' AND
               (NEW.project_index_ref IS NULL
                OR project_index.embedding_index_id IS NULL
                OR project_index.scope<>'PROJECT'
                OR project_index.project_id<>NEW.project_id
                OR project_index.index_state<>'ACTIVE'))
           OR NEW.created_xid<>txid_current() THEN
            RAISE EXCEPTION 'RAG RetrievalRun foundation binding is invalid';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.retrieval_state<>'RUNNING'
       OR NEW.retrieval_state NOT IN ('SUCCEEDED','FAILED')
       OR OLD.lock_version<>0 OR NEW.lock_version<>1
       OR ROW(NEW.retrieval_run_id,NEW.scope,NEW.project_id,NEW.actor_ref,
              NEW.query_fingerprint,NEW.metadata_filter,
              NEW.metadata_filter_fingerprint,NEW.global_index_ref,
              NEW.project_index_ref,NEW.retrieval_policy_ref,
              NEW.rerank_policy_ref,NEW.top_k,NEW.job_id,NEW.trace_id,
              NEW.created_at,NEW.created_xid)
          IS DISTINCT FROM
          ROW(OLD.retrieval_run_id,OLD.scope,OLD.project_id,OLD.actor_ref,
              OLD.query_fingerprint,OLD.metadata_filter,
              OLD.metadata_filter_fingerprint,OLD.global_index_ref,
              OLD.project_index_ref,OLD.retrieval_policy_ref,
              OLD.rerank_policy_ref,OLD.top_k,OLD.job_id,OLD.trace_id,
              OLD.created_at,OLD.created_xid)
       OR NEW.scope<>'PROJECT' OR NEW.global_index_ref IS NOT NULL
       OR NEW.retrieval_policy_ref<>'fts.project.v1'
       OR NEW.rerank_policy_ref<>'none.v1'
       OR job_row.job_id IS NULL OR job_row.owner_module<>'rag'
       OR job_row.job_type<>'RAG_RETRIEVAL'
       OR ROW(job_row.scope,job_row.project_id,job_row.actor_ref,job_row.trace_id)
          IS DISTINCT FROM ROW(NEW.scope,NEW.project_id,NEW.actor_ref,
                               NEW.trace_id::text)
       OR job_row.payload_refs<>jsonb_build_object(
            'retrieval_run_id',NEW.retrieval_run_id::text)
       OR (NEW.retrieval_state='SUCCEEDED' AND
           (project_state IS DISTINCT FROM 'ACTIVE'
            OR project_index.embedding_index_id IS NULL
            OR project_index.scope<>'PROJECT'
            OR project_index.project_id<>NEW.project_id
            OR project_index.index_state<>'ACTIVE')) THEN
        RAISE EXCEPTION 'RAG RetrievalRun terminal transition is invalid';
    END IF;
    RETURN NEW;
END; $$;
"""


_TERMINAL_VALIDATOR = r"""
CREATE FUNCTION plm.validate_rag_retrieval_terminal_transaction()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    target_run_id uuid;
    run_row plm.rag_retrieval_runs%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
    lease_row plm.job_leases%ROWTYPE;
    attempt_row plm.job_attempts%ROWTYPE;
    index_row plm.rag_embedding_indexes%ROWTYPE;
    bundle_row plm.rag_context_bundles%ROWTYPE;
    candidate_count integer;
    score_count integer;
    bundle_count integer;
    item_count integer;
    total_token_count bigint;
BEGIN
    IF TG_TABLE_NAME='job_jobs' THEN
        IF NEW.owner_module<>'rag' OR NEW.job_type<>'RAG_RETRIEVAL'
           OR NEW.state NOT IN ('SUCCEEDED','FAILED') THEN
            RETURN NULL;
        END IF;
        SELECT retrieval_run_id INTO target_run_id FROM plm.rag_retrieval_runs
         WHERE job_id=NEW.job_id;
        IF target_run_id IS NULL THEN
            RAISE EXCEPTION 'RAG Retrieval terminal transaction is incomplete';
        END IF;
    ELSE
        target_run_id := NEW.retrieval_run_id;
    END IF;
    SELECT * INTO run_row FROM plm.rag_retrieval_runs
     WHERE retrieval_run_id=target_run_id;
    IF run_row.retrieval_run_id IS NULL THEN
        RAISE EXCEPTION 'RAG Retrieval terminal transaction is incomplete';
    END IF;
    IF run_row.retrieval_state='RUNNING' THEN
        IF TG_TABLE_NAME IN ('rag_retrieval_candidates',
                             'rag_retrieval_score_parts',
                             'rag_context_bundles','rag_context_items') THEN
            RAISE EXCEPTION 'RAG Retrieval result cannot commit before terminal state';
        END IF;
        RETURN NULL;
    END IF;
    SELECT * INTO job_row FROM plm.job_jobs WHERE job_id=run_row.job_id;
    SELECT * INTO lease_row FROM plm.job_leases
     WHERE job_id=run_row.job_id AND fencing_token=1;
    SELECT * INTO attempt_row FROM plm.job_attempts
     WHERE job_id=run_row.job_id AND fencing_token=1;
    IF run_row.project_index_ref IS NOT NULL THEN
        SELECT * INTO index_row FROM plm.rag_embedding_indexes
         WHERE embedding_index_id=run_row.project_index_ref;
    END IF;
    IF job_row.job_id IS NULL OR job_row.owner_module<>'rag'
       OR job_row.job_type<>'RAG_RETRIEVAL'
       OR job_row.state<>run_row.retrieval_state
       OR job_row.max_attempts<>1 OR job_row.attempt_count<>1
       OR job_row.fencing_token<>1 OR job_row.lock_version<>2
       OR job_row.lease_expires_at IS NOT NULL
       OR job_row.completed_at IS DISTINCT FROM run_row.completed_at
       OR ROW(job_row.scope,job_row.project_id,job_row.actor_ref,job_row.trace_id)
          IS DISTINCT FROM ROW(run_row.scope,run_row.project_id,
                               run_row.actor_ref,run_row.trace_id::text)
       OR job_row.payload_refs<>jsonb_build_object(
            'retrieval_run_id',run_row.retrieval_run_id::text)
       OR lease_row.lease_id IS NULL OR lease_row.fencing_token<>1
       OR attempt_row.attempt_id IS NULL OR attempt_row.attempt_no<>1
       OR attempt_row.fencing_token<>1
       OR attempt_row.worker_ref<>lease_row.worker_ref
       OR attempt_row.completed_at IS DISTINCT FROM run_row.completed_at
       OR attempt_row.started_at>run_row.completed_at
       OR lease_row.acquired_at>run_row.completed_at THEN
        RAISE EXCEPTION 'RAG Retrieval Job terminal binding is invalid';
    END IF;
    SELECT count(*) INTO candidate_count FROM plm.rag_retrieval_candidates
     WHERE retrieval_run_id=target_run_id;
    SELECT count(*) INTO score_count FROM plm.rag_retrieval_score_parts
     WHERE retrieval_run_id=target_run_id;
    SELECT count(*) INTO bundle_count FROM plm.rag_context_bundles
     WHERE retrieval_run_id=target_run_id;
    SELECT count(*) INTO item_count FROM plm.rag_context_items
     WHERE retrieval_run_id=target_run_id;
    IF run_row.retrieval_state='FAILED' THEN
        IF attempt_row.error_code IS DISTINCT FROM run_row.error_code
           OR (run_row.error_code='RAG_RETRIEVAL_LEASE_EXPIRED' AND
               (lease_row.state<>'EXPIRED'
                OR lease_row.lease_expires_at>run_row.completed_at))
           OR (run_row.error_code<>'RAG_RETRIEVAL_LEASE_EXPIRED' AND
               (lease_row.state<>'RELEASED'
                OR lease_row.lease_expires_at<=run_row.completed_at))
           OR candidate_count<>0 OR score_count<>0
           OR bundle_count<>0 OR item_count<>0 THEN
            RAISE EXCEPTION 'RAG Retrieval failed terminal transaction is invalid';
        END IF;
        RETURN NULL;
    END IF;
    IF run_row.retrieval_state<>'SUCCEEDED'
       OR lease_row.state<>'RELEASED'
       OR lease_row.lease_expires_at<=run_row.completed_at
       OR attempt_row.error_code IS NOT NULL
       OR index_row.embedding_index_id IS NULL
       OR index_row.scope<>'PROJECT'
       OR index_row.project_id<>run_row.project_id
       OR index_row.index_state<>'ACTIVE'
       OR candidate_count<1 OR candidate_count>run_row.top_k
       OR score_count<>candidate_count*2
       OR bundle_count<>1 OR item_count<>candidate_count THEN
        RAISE EXCEPTION 'RAG Retrieval success terminal transaction is incomplete';
    END IF;
    IF EXISTS (
        SELECT 1 FROM plm.rag_retrieval_candidates candidate
         WHERE candidate.retrieval_run_id=target_run_id
           AND (candidate.candidate_scope<>'PROJECT'
                OR candidate.candidate_project_id<>run_row.project_id
                OR candidate.run_project_id<>run_row.project_id
                OR candidate.embedding_index_id<>run_row.project_index_ref
                OR candidate.retrieval_channel<>'FTS'
                OR candidate.final_score_micros<=0
                OR candidate.created_xid<>txid_current()))
       OR (SELECT min(candidate_ordinal) FROM plm.rag_retrieval_candidates
            WHERE retrieval_run_id=target_run_id)<>0
       OR (SELECT max(candidate_ordinal) FROM plm.rag_retrieval_candidates
            WHERE retrieval_run_id=target_run_id)<>candidate_count-1
       OR EXISTS (
        SELECT 1 FROM plm.rag_retrieval_candidates candidate
         WHERE candidate.retrieval_run_id=target_run_id AND (
           (SELECT count(*) FROM plm.rag_retrieval_score_parts score
             WHERE score.candidate_id=candidate.candidate_id)<>2
           OR NOT EXISTS (
             SELECT 1 FROM plm.rag_retrieval_score_parts score
              WHERE score.candidate_id=candidate.candidate_id
                AND score.score_kind='FTS' AND score.score_ordinal=0
                AND score.score_policy_ref=run_row.retrieval_policy_ref
                AND score.raw_score_micros=candidate.final_score_micros
                AND score.normalized_score_micros=
                    LEAST(candidate.final_score_micros,1000000)
                AND score.weight_micros=1000000
                AND score.weighted_score_micros=candidate.final_score_micros
                AND score.created_xid=txid_current())
           OR NOT EXISTS (
             SELECT 1 FROM plm.rag_retrieval_score_parts score
              WHERE score.candidate_id=candidate.candidate_id
                AND score.score_kind='FINAL' AND score.score_ordinal=1
                AND score.score_policy_ref=run_row.retrieval_policy_ref
                AND score.raw_score_micros=candidate.final_score_micros
                AND score.normalized_score_micros=
                    LEAST(candidate.final_score_micros,1000000)
                AND score.weight_micros=1000000
                AND score.weighted_score_micros=candidate.final_score_micros
                AND score.created_xid=txid_current()))) THEN
        RAISE EXCEPTION 'RAG Retrieval candidate and score set is incomplete';
    END IF;
    SELECT * INTO bundle_row FROM plm.rag_context_bundles
     WHERE retrieval_run_id=target_run_id;
    SELECT coalesce(sum(item.token_count),0) INTO total_token_count
      FROM plm.rag_context_items item
     WHERE item.retrieval_run_id=target_run_id;
    IF bundle_row.context_bundle_id IS NULL
       OR bundle_row.project_id<>run_row.project_id
       OR bundle_row.context_policy_ref<>'project-documents.v1'
       OR bundle_row.item_count<>candidate_count
       OR bundle_row.token_count<>total_token_count
       OR bundle_row.created_xid<>txid_current()
       OR (SELECT min(item_ordinal) FROM plm.rag_context_items
            WHERE retrieval_run_id=target_run_id)<>0
       OR (SELECT max(item_ordinal) FROM plm.rag_context_items
            WHERE retrieval_run_id=target_run_id)<>candidate_count-1
       OR EXISTS (
          SELECT 1 FROM plm.rag_retrieval_candidates candidate
           WHERE candidate.retrieval_run_id=target_run_id
             AND NOT EXISTS (
               SELECT 1 FROM plm.rag_context_items item
                WHERE item.retrieval_run_id=target_run_id
                  AND item.context_bundle_id=bundle_row.context_bundle_id
                  AND item.candidate_id=candidate.candidate_id
                  AND item.item_ordinal=candidate.candidate_ordinal
                  AND item.access_snapshot_fingerprint=
                      candidate.authorization_snapshot_fingerprint
                  AND item.created_xid=txid_current())) THEN
        RAISE EXCEPTION 'RAG minimal Context transaction is incomplete';
    END IF;
    IF (candidate_count<run_row.top_k)
       IS DISTINCT FROM
       (run_row.quality_flags='["CANDIDATE_SHORTFALL"]'::jsonb) THEN
        RAISE EXCEPTION 'RAG Retrieval quality flags are inconsistent';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_retrieval_run_terminal_complete
AFTER UPDATE ON plm.rag_retrieval_runs
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_terminal_transaction();

CREATE CONSTRAINT TRIGGER trg_rag_retrieval_job_terminal_complete
AFTER UPDATE ON plm.job_jobs
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_terminal_transaction();

CREATE CONSTRAINT TRIGGER trg_rag_retrieval_candidate_terminal_complete
AFTER INSERT ON plm.rag_retrieval_candidates
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_terminal_transaction();

CREATE CONSTRAINT TRIGGER trg_rag_retrieval_score_terminal_complete
AFTER INSERT ON plm.rag_retrieval_score_parts
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_terminal_transaction();

CREATE CONSTRAINT TRIGGER trg_rag_context_bundle_terminal_complete
AFTER INSERT ON plm.rag_context_bundles
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_terminal_transaction();

CREATE CONSTRAINT TRIGGER trg_rag_context_item_terminal_complete
AFTER INSERT ON plm.rag_context_items
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_terminal_transaction();
"""


def _previous_run_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions."
        "20261004_0088_rag_retrieval_foundation"
    )
    source = previous._GUARDS
    start = source.index(
        "CREATE FUNCTION plm.guard_rag_retrieval_run_foundation()"
    )
    end = source.index(
        "CREATE TRIGGER trg_rag_retrieval_run_foundation_guard", start
    )
    return source[start:end].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def upgrade() -> None:
    op.drop_constraint(
        "ck_rag_retrieval_runs__foundation_state", "rag_retrieval_runs",
        schema="plm", type_="check",
    )
    op.create_check_constraint(
        "ck_rag_retrieval_runs__lifecycle", "rag_retrieval_runs",
        _RUN_STATE_CHECK, schema="plm",
    )
    op.execute(_RUN_GUARD)
    op.execute(_TERMINAL_VALIDATOR)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Retrieval terminal downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.job_jobs, plm.job_attempts, plm.job_leases, "
        "plm.rag_context_items, plm.rag_context_bundles, "
        "plm.rag_retrieval_score_parts, plm.rag_retrieval_candidates, "
        "plm.rag_retrieval_runs IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_retrieval_runs
                        WHERE retrieval_state<>'RUNNING')
               OR EXISTS (SELECT 1 FROM plm.rag_retrieval_candidates)
               OR EXISTS (SELECT 1 FROM plm.rag_retrieval_score_parts)
               OR EXISTS (SELECT 1 FROM plm.rag_context_bundles)
               OR EXISTS (SELECT 1 FROM plm.rag_context_items) THEN
                RAISE EXCEPTION 'terminal RAG Retrieval history prevents downgrade';
            END IF;
        END $$;
    """)
    for trigger, table in (
        ("trg_rag_context_item_terminal_complete", "rag_context_items"),
        ("trg_rag_context_bundle_terminal_complete", "rag_context_bundles"),
        ("trg_rag_retrieval_score_terminal_complete", "rag_retrieval_score_parts"),
        ("trg_rag_retrieval_candidate_terminal_complete", "rag_retrieval_candidates"),
        ("trg_rag_retrieval_job_terminal_complete", "job_jobs"),
        ("trg_rag_retrieval_run_terminal_complete", "rag_retrieval_runs"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON plm.{table}")
    op.execute("DROP FUNCTION plm.validate_rag_retrieval_terminal_transaction()")
    op.execute(_previous_run_guard())
    op.drop_constraint(
        "ck_rag_retrieval_runs__lifecycle", "rag_retrieval_runs",
        schema="plm", type_="check",
    )
    op.create_check_constraint(
        "ck_rag_retrieval_runs__foundation_state", "rag_retrieval_runs",
        "top_k BETWEEN 1 AND 100 AND "
        "rerank_state IN ('PENDING','NOT_APPLICABLE') AND "
        "egress_state IN ('PENDING','NOT_APPLICABLE') AND "
        "retrieval_state='RUNNING' AND jsonb_typeof(quality_flags)='array' AND "
        "NOT degraded AND error_code IS NULL AND completed_at IS NULL AND "
        "created_xid>0 AND lock_version=0 AND isfinite(created_at)",
        schema="plm",
    )
