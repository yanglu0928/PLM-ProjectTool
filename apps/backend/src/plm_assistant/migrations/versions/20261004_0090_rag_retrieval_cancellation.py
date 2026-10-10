"""Add atomic cancellation boundary for RAG Retrieval.

Revision ID: 20261004_0090
Revises: 20261004_0089
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261004_0090"
down_revision = "20261004_0089"
branch_labels = None
depends_on = None


_previous = importlib.import_module(
    "plm_assistant.migrations.versions.20261004_0089_rag_retrieval_terminal"
)

_RUN_STATE_CHECK = _previous._RUN_STATE_CHECK.replace(
    "  (retrieval_state='FAILED' AND rerank_state='NOT_APPLICABLE'",
    "  (retrieval_state='CANCELLED' AND rerank_state='NOT_APPLICABLE'\n"
    "   AND egress_state='NOT_APPLICABLE' AND quality_flags='[]'::jsonb\n"
    "   AND error_code IS NULL AND completed_at IS NOT NULL\n"
    "   AND isfinite(completed_at) AND completed_at>=created_at AND lock_version=1)\n"
    "  OR\n"
    "  (retrieval_state='FAILED' AND rerank_state='NOT_APPLICABLE'",
)

_RUN_GUARD = _previous._RUN_GUARD.replace(
    "NEW.retrieval_state NOT IN ('SUCCEEDED','FAILED')",
    "NEW.retrieval_state NOT IN ('SUCCEEDED','FAILED','CANCELLED')",
)

_CANCEL_VALIDATION = r"""
    IF run_row.retrieval_state='CANCELLED' THEN
        IF job_row.job_id IS NULL OR job_row.owner_module<>'rag'
           OR job_row.job_type<>'RAG_RETRIEVAL'
           OR job_row.state<>'CANCELLED'
           OR job_row.max_attempts<>1 OR job_row.lease_expires_at IS NOT NULL
           OR job_row.completed_at IS DISTINCT FROM run_row.completed_at
           OR job_row.cancel_requested_by IS NULL
           OR job_row.cancel_requested_at IS NULL
           OR job_row.cancel_reason IS NULL
           OR job_row.cancel_requested_at>run_row.completed_at
           OR ROW(job_row.scope,job_row.project_id,job_row.actor_ref,job_row.trace_id)
              IS DISTINCT FROM ROW(run_row.scope,run_row.project_id,
                                   run_row.actor_ref,run_row.trace_id::text)
           OR job_row.payload_refs<>jsonb_build_object(
                'retrieval_run_id',run_row.retrieval_run_id::text)
           OR EXISTS (SELECT 1 FROM plm.rag_retrieval_candidates
                       WHERE retrieval_run_id=target_run_id)
           OR EXISTS (SELECT 1 FROM plm.rag_retrieval_score_parts
                       WHERE retrieval_run_id=target_run_id)
           OR EXISTS (SELECT 1 FROM plm.rag_context_bundles
                       WHERE retrieval_run_id=target_run_id)
           OR EXISTS (SELECT 1 FROM plm.rag_context_items
                       WHERE retrieval_run_id=target_run_id)
           OR NOT (
             (job_row.attempt_count=0 AND job_row.fencing_token=0
              AND job_row.lock_version=2
              AND lease_row.lease_id IS NULL AND attempt_row.attempt_id IS NULL)
             OR
             (job_row.attempt_count=1 AND job_row.fencing_token=1
              AND job_row.lock_version=3
              AND lease_row.lease_id IS NOT NULL
              AND lease_row.fencing_token=1
              AND lease_row.state IN ('RELEASED','EXPIRED')
              AND attempt_row.attempt_id IS NOT NULL
              AND attempt_row.attempt_no=1 AND attempt_row.fencing_token=1
              AND attempt_row.worker_ref=lease_row.worker_ref
              AND attempt_row.completed_at IS NOT DISTINCT FROM run_row.completed_at
              AND attempt_row.error_code='JOB_CANCELLED'
              AND lease_row.acquired_at<=job_row.cancel_requested_at
              AND ((lease_row.state='RELEASED'
                    AND lease_row.lease_expires_at>run_row.completed_at)
                   OR (lease_row.state='EXPIRED'
                       AND lease_row.lease_expires_at<=run_row.completed_at)))
           ) THEN
            RAISE EXCEPTION 'RAG Retrieval cancelled terminal transaction is invalid';
        END IF;
        RETURN NULL;
    END IF;
"""

_TERMINAL_ANCHOR = """    IF job_row.job_id IS NULL OR job_row.owner_module<>'rag'
       OR job_row.job_type<>'RAG_RETRIEVAL'
"""
if _TERMINAL_ANCHOR not in _previous._TERMINAL_VALIDATOR:
    raise RuntimeError("Schema0089 terminal validator anchor missing")
_RUNNING_BRANCH = """    IF run_row.retrieval_state='RUNNING' THEN
        IF TG_TABLE_NAME IN ('rag_retrieval_candidates',
                             'rag_retrieval_score_parts',
                             'rag_context_bundles','rag_context_items') THEN
            RAISE EXCEPTION 'RAG Retrieval result cannot commit before terminal state';
        END IF;
        RETURN NULL;
    END IF;
"""
_STRICT_RUNNING_BRANCH = """    IF run_row.retrieval_state='RUNNING' THEN
        IF TG_TABLE_NAME IN ('rag_retrieval_candidates',
                             'rag_retrieval_score_parts',
                             'rag_context_bundles','rag_context_items') THEN
            RAISE EXCEPTION 'RAG Retrieval result cannot commit before terminal state';
        ELSIF TG_TABLE_NAME='job_jobs'
              AND NEW.state IN ('SUCCEEDED','FAILED','CANCELLED') THEN
            RAISE EXCEPTION 'RAG Retrieval terminal transaction is incomplete';
        END IF;
        RETURN NULL;
    END IF;
"""
if _RUNNING_BRANCH not in _previous._TERMINAL_VALIDATOR:
    raise RuntimeError("Schema0089 running validator anchor missing")
_TERMINAL_VALIDATOR = _previous._TERMINAL_VALIDATOR.replace(
    "NEW.state NOT IN ('SUCCEEDED','FAILED')",
    "NEW.state NOT IN ('SUCCEEDED','FAILED','CANCELLED')",
).replace(
    _RUNNING_BRANCH,
    _STRICT_RUNNING_BRANCH,
    1,
).replace(
    _TERMINAL_ANCHOR,
    _CANCEL_VALIDATION + _TERMINAL_ANCHOR,
    1,
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_rag_retrieval_runs__lifecycle", "rag_retrieval_runs",
        schema="plm", type_="check",
    )
    op.create_check_constraint(
        "ck_rag_retrieval_runs__lifecycle", "rag_retrieval_runs",
        _RUN_STATE_CHECK, schema="plm",
    )
    op.execute(_RUN_GUARD)
    op.execute(
        "DROP FUNCTION plm.validate_rag_retrieval_terminal_transaction() CASCADE"
    )
    op.execute(_TERMINAL_VALIDATOR)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Retrieval cancellation downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.job_jobs, plm.job_attempts, plm.job_leases, "
        "plm.rag_context_items, plm.rag_context_bundles, "
        "plm.rag_retrieval_score_parts, plm.rag_retrieval_candidates, "
        "plm.rag_retrieval_runs IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_retrieval_runs
                        WHERE retrieval_state='CANCELLED')
               OR EXISTS (
                    SELECT 1 FROM plm.job_jobs
                     WHERE owner_module='rag' AND job_type='RAG_RETRIEVAL'
                       AND (state IN ('CANCEL_REQUESTED','CANCELLED')
                            OR cancel_requested_by IS NOT NULL)) THEN
                RAISE EXCEPTION
                  'cancelled RAG Retrieval history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute(
        "DROP FUNCTION plm.validate_rag_retrieval_terminal_transaction() CASCADE"
    )
    op.execute(_previous._TERMINAL_VALIDATOR)
    op.execute(_previous._RUN_GUARD)
    op.drop_constraint(
        "ck_rag_retrieval_runs__lifecycle", "rag_retrieval_runs",
        schema="plm", type_="check",
    )
    op.create_check_constraint(
        "ck_rag_retrieval_runs__lifecycle", "rag_retrieval_runs",
        _previous._RUN_STATE_CHECK, schema="plm",
    )
