"""Add immutable RetrievalRun, candidate and minimal Context foundation.

Revision ID: 20261004_0088
Revises: 20261004_0087
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261004_0088"
down_revision = "20261004_0087"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_retrieval_run_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    project_state text;
    job_row plm.job_jobs%ROWTYPE;
    global_index plm.rag_embedding_indexes%ROWTYPE;
    project_index plm.rag_embedding_indexes%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG RetrievalRun state Owner is not installed';
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
END; $$;

CREATE TRIGGER trg_rag_retrieval_run_foundation_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_retrieval_runs
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_retrieval_run_foundation();

CREATE FUNCTION plm.guard_rag_retrieval_query_content()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE run_row plm.rag_retrieval_runs%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Retrieval query content is retained';
    END IF;
    SELECT * INTO run_row FROM plm.rag_retrieval_runs
     WHERE retrieval_run_id=NEW.retrieval_run_id FOR KEY SHARE;
    IF run_row.retrieval_run_id IS NULL
       OR run_row.project_id IS DISTINCT FROM NEW.project_id
       OR run_row.query_fingerprint<>NEW.query_fingerprint
       OR run_row.created_xid<>NEW.created_xid
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG Retrieval query content binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_retrieval_query_content_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_retrieval_query_contents
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_retrieval_query_content();

CREATE FUNCTION plm.validate_rag_retrieval_query_content()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE content_row plm.rag_retrieval_query_contents%ROWTYPE;
BEGIN
    SELECT * INTO content_row FROM plm.rag_retrieval_query_contents
     WHERE retrieval_run_id=NEW.retrieval_run_id;
    IF content_row.retrieval_run_id IS NULL
       OR content_row.project_id IS DISTINCT FROM NEW.project_id
       OR content_row.query_fingerprint<>NEW.query_fingerprint
       OR content_row.created_xid<>NEW.created_xid THEN
        RAISE EXCEPTION 'RAG RetrievalRun query content is incomplete';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_retrieval_query_content_complete
AFTER INSERT ON plm.rag_retrieval_runs
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.validate_rag_retrieval_query_content();

CREATE FUNCTION plm.guard_rag_retrieval_candidate()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    run_row plm.rag_retrieval_runs%ROWTYPE;
    index_row plm.rag_embedding_indexes%ROWTYPE;
    chunk_row plm.rag_document_chunks%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Retrieval candidate history is retained';
    END IF;
    SELECT * INTO run_row FROM plm.rag_retrieval_runs
     WHERE retrieval_run_id=NEW.retrieval_run_id FOR KEY SHARE;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO chunk_row FROM plm.rag_document_chunks
     WHERE chunk_id=NEW.chunk_id FOR KEY SHARE;
    IF run_row.retrieval_run_id IS NULL OR run_row.retrieval_state<>'RUNNING'
       OR run_row.project_id IS DISTINCT FROM NEW.run_project_id
       OR index_row.embedding_index_id IS NULL
       OR index_row.index_state<>'ACTIVE'
       OR ROW(index_row.scope,index_row.project_id,index_row.embedding_model_ref)
          IS DISTINCT FROM
          ROW(NEW.candidate_scope,NEW.candidate_project_id,
              NEW.embedding_model_ref)
       OR chunk_row.chunk_id IS NULL OR chunk_row.chunk_state<>'ACTIVE'
       OR ROW(chunk_row.scope,chunk_row.project_id,
              chunk_row.document_version_ref,chunk_row.parse_result_ref,
              chunk_row.source_type,chunk_row.source_locator)
          IS DISTINCT FROM
          ROW(NEW.candidate_scope,NEW.candidate_project_id,
              NEW.document_version_ref,NEW.parse_result_ref,
              NEW.source_type,NEW.source_locator)
       OR (NEW.candidate_scope='GLOBAL' AND
           run_row.global_index_ref IS DISTINCT FROM NEW.embedding_index_id)
       OR (NEW.candidate_scope='PROJECT' AND
           (run_row.scope<>'PROJECT'
            OR run_row.project_index_ref IS DISTINCT FROM NEW.embedding_index_id
            OR run_row.project_id IS DISTINCT FROM NEW.candidate_project_id))
       OR NOT EXISTS (
            SELECT 1 FROM plm.rag_index_source_chunks source
             WHERE source.embedding_index_id=NEW.embedding_index_id
               AND source.chunk_id=NEW.chunk_id
               AND source.chunk_text_fingerprint=chunk_row.text_fingerprint)
       OR NOT EXISTS (
            SELECT 1 FROM plm.rag_embedding_records record
             WHERE record.embedding_index_id=NEW.embedding_index_id
               AND record.chunk_id=NEW.chunk_id
               AND record.embedding_state='AVAILABLE')
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG Retrieval candidate binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_retrieval_candidate_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_retrieval_candidates
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_retrieval_candidate();

CREATE FUNCTION plm.guard_rag_retrieval_score_part()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE candidate_row plm.rag_retrieval_candidates%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Retrieval score history is retained';
    END IF;
    SELECT * INTO candidate_row FROM plm.rag_retrieval_candidates
     WHERE candidate_id=NEW.candidate_id FOR KEY SHARE;
    IF candidate_row.candidate_id IS NULL
       OR candidate_row.retrieval_run_id<>NEW.retrieval_run_id
       OR candidate_row.run_project_id IS DISTINCT FROM NEW.project_id
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG Retrieval score binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_retrieval_score_part_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_retrieval_score_parts
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_retrieval_score_part();

CREATE FUNCTION plm.guard_rag_context_bundle()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE run_row plm.rag_retrieval_runs%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG ContextBundle history is retained';
    END IF;
    SELECT * INTO run_row FROM plm.rag_retrieval_runs
     WHERE retrieval_run_id=NEW.retrieval_run_id FOR KEY SHARE;
    IF run_row.retrieval_run_id IS NULL
       OR run_row.retrieval_state<>'SUCCEEDED'
       OR run_row.project_id IS DISTINCT FROM NEW.project_id
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG ContextBundle Owner is not installed';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_context_bundle_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_context_bundles
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_context_bundle();

CREATE FUNCTION plm.guard_rag_context_item()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    bundle_row plm.rag_context_bundles%ROWTYPE;
    candidate_row plm.rag_retrieval_candidates%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Context item history is retained';
    END IF;
    SELECT * INTO bundle_row FROM plm.rag_context_bundles
     WHERE context_bundle_id=NEW.context_bundle_id FOR KEY SHARE;
    SELECT * INTO candidate_row FROM plm.rag_retrieval_candidates
     WHERE candidate_id=NEW.candidate_id FOR KEY SHARE;
    IF bundle_row.context_bundle_id IS NULL
       OR candidate_row.candidate_id IS NULL
       OR bundle_row.retrieval_run_id<>NEW.retrieval_run_id
       OR candidate_row.retrieval_run_id<>NEW.retrieval_run_id
       OR bundle_row.project_id IS DISTINCT FROM NEW.project_id
       OR candidate_row.run_project_id IS DISTINCT FROM NEW.project_id
       OR candidate_row.chunk_id<>NEW.chunk_id
       OR candidate_row.document_version_ref<>NEW.document_version_ref
       OR candidate_row.source_locator<>NEW.source_locator
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG Context item binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_context_item_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_context_items
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_context_item();

CREATE FUNCTION plm.guard_rag_retrieval_foundation_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    RAISE EXCEPTION 'RAG Retrieval and Context history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_retrieval_runs_no_truncate BEFORE TRUNCATE
ON plm.rag_retrieval_runs FOR EACH STATEMENT
EXECUTE FUNCTION plm.guard_rag_retrieval_foundation_truncate();
CREATE TRIGGER trg_rag_retrieval_query_contents_no_truncate BEFORE TRUNCATE
ON plm.rag_retrieval_query_contents FOR EACH STATEMENT
EXECUTE FUNCTION plm.guard_rag_retrieval_foundation_truncate();
CREATE TRIGGER trg_rag_retrieval_candidates_no_truncate BEFORE TRUNCATE
ON plm.rag_retrieval_candidates FOR EACH STATEMENT
EXECUTE FUNCTION plm.guard_rag_retrieval_foundation_truncate();
CREATE TRIGGER trg_rag_retrieval_score_parts_no_truncate BEFORE TRUNCATE
ON plm.rag_retrieval_score_parts FOR EACH STATEMENT
EXECUTE FUNCTION plm.guard_rag_retrieval_foundation_truncate();
CREATE TRIGGER trg_rag_context_bundles_no_truncate BEFORE TRUNCATE
ON plm.rag_context_bundles FOR EACH STATEMENT
EXECUTE FUNCTION plm.guard_rag_retrieval_foundation_truncate();
CREATE TRIGGER trg_rag_context_items_no_truncate BEFORE TRUNCATE
ON plm.rag_context_items FOR EACH STATEMENT
EXECUTE FUNCTION plm.guard_rag_retrieval_foundation_truncate();
"""


def _ref_check(column: str, maximum: int = 127) -> str:
    return f"{column} ~ '^[A-Za-z][A-Za-z0-9._:/-]{{0,{maximum}}}$'"


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "rag_retrieval_runs",
        sa.Column("retrieval_run_id", ident, primary_key=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("actor_ref", ident, nullable=False),
        sa.Column("query_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("metadata_filter", postgresql.JSONB(), nullable=False),
        sa.Column("metadata_filter_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("global_index_ref", ident),
        sa.Column("project_index_ref", ident),
        sa.Column("retrieval_policy_ref", sa.Text(), nullable=False),
        sa.Column("rerank_policy_ref", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("rerank_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("egress_state", sa.Text(), nullable=False),
        sa.Column("retrieval_state", sa.Text(), nullable=False,
                  server_default=sa.text("'RUNNING'")),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("degraded", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("error_code", sa.Text()),
        sa.Column("job_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("completed_at", timestamp),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_retrieval_runs__project"),
        sa.ForeignKeyConstraint(["actor_ref"], ["plm.auth_users.user_id"],
                                name="fk_rag_retrieval_runs__actor"),
        sa.ForeignKeyConstraint(["global_index_ref"],
                                ["plm.rag_embedding_indexes.embedding_index_id"],
                                name="fk_rag_retrieval_runs__global_index"),
        sa.ForeignKeyConstraint(["project_index_ref"],
                                ["plm.rag_embedding_indexes.embedding_index_id"],
                                name="fk_rag_retrieval_runs__project_index"),
        sa.ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"],
                                name="fk_rag_retrieval_runs__job"),
        sa.UniqueConstraint("job_id", name="uq_rag_retrieval_runs__job"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL AND global_index_ref IS NOT NULL "
            "AND project_index_ref IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL "
            "AND project_index_ref IS NOT NULL)",
            name="ck_rag_retrieval_runs__scope_project"),
        sa.CheckConstraint(
            "octet_length(query_fingerprint)=32 AND "
            "octet_length(metadata_filter_fingerprint)=32 AND "
            "jsonb_typeof(metadata_filter)='object' AND "
            "(metadata_filter - ARRAY['document_category','source_type',"
            "'document_version_ref','effective_from','effective_to','business']::text[])="
            "'{}'::jsonb",
            name="ck_rag_retrieval_runs__query_filter"),
        sa.CheckConstraint(
            _ref_check("retrieval_policy_ref") + " AND " +
            _ref_check("rerank_policy_ref"),
            name="ck_rag_retrieval_runs__policies"),
        sa.CheckConstraint(
            "top_k BETWEEN 1 AND 100 AND "
            "rerank_state IN ('PENDING','NOT_APPLICABLE') AND "
            "egress_state IN ('PENDING','NOT_APPLICABLE') AND "
            "retrieval_state='RUNNING' AND jsonb_typeof(quality_flags)='array' AND "
            "NOT degraded AND error_code IS NULL AND completed_at IS NULL AND "
            "created_xid>0 AND lock_version=0 AND isfinite(created_at)",
            name="ck_rag_retrieval_runs__foundation_state"),
        schema="plm",
    )
    op.create_index("ix_rag_retrieval_runs__project_time", "rag_retrieval_runs",
                    ["project_id", sa.text("created_at DESC"),
                     sa.text("retrieval_run_id DESC")], schema="plm")
    op.create_table(
        "rag_retrieval_query_contents",
        sa.Column("retrieval_run_id", ident, primary_key=True),
        sa.Column("project_id", ident),
        sa.Column("query_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("key_provider_ref", sa.Text(), nullable=False),
        sa.Column("plaintext_bytes", sa.Integer(), nullable=False),
        sa.Column("retention_until", timestamp, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["retrieval_run_id"],
                                ["plm.rag_retrieval_runs.retrieval_run_id"],
                                name="fk_rag_retrieval_query_contents__run"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_retrieval_query_contents__project"),
        sa.CheckConstraint(
            "octet_length(query_fingerprint)=32 AND "
            "octet_length(encrypted_payload) BETWEEN 17 AND 65536 AND "
            "jsonb_typeof(encryption_metadata)='object' AND "
            "encryption_metadata ? 'format' AND encryption_metadata ? 'nonce' AND "
            + _ref_check("key_provider_ref", 255),
            name="ck_rag_retrieval_query_contents__cipher"),
        sa.CheckConstraint(
            "plaintext_bytes BETWEEN 1 AND 16384 AND created_xid>0 AND "
            "isfinite(created_at) AND isfinite(retention_until) AND "
            "retention_until>created_at",
            name="ck_rag_retrieval_query_contents__retention"),
        schema="plm",
    )
    op.create_table(
        "rag_retrieval_candidates",
        sa.Column("candidate_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("retrieval_run_id", ident, nullable=False),
        sa.Column("run_project_id", ident),
        sa.Column("candidate_scope", sa.Text(), nullable=False),
        sa.Column("candidate_project_id", ident),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("embedding_model_ref", ident, nullable=False),
        sa.Column("chunk_id", ident, nullable=False),
        sa.Column("document_version_ref", ident, nullable=False),
        sa.Column("parse_result_ref", ident, nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
        sa.Column("retrieval_channel", sa.Text(), nullable=False),
        sa.Column("candidate_ordinal", sa.Integer(), nullable=False),
        sa.Column("final_score_micros", sa.BigInteger(), nullable=False),
        sa.Column("authorization_snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["retrieval_run_id"],
                                ["plm.rag_retrieval_runs.retrieval_run_id"],
                                name="fk_rag_retrieval_candidates__run"),
        sa.ForeignKeyConstraint(["run_project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_retrieval_candidates__run_project"),
        sa.ForeignKeyConstraint(["candidate_project_id"],
                                ["plm.prj_projects.project_id"],
                                name="fk_rag_retrieval_candidates__candidate_project"),
        sa.ForeignKeyConstraint(["embedding_index_id"],
                                ["plm.rag_embedding_indexes.embedding_index_id"],
                                name="fk_rag_retrieval_candidates__index"),
        sa.ForeignKeyConstraint(["embedding_model_ref"],
                                ["plm.ai_models.ai_model_id"],
                                name="fk_rag_retrieval_candidates__model"),
        sa.ForeignKeyConstraint(["chunk_id"], ["plm.rag_document_chunks.chunk_id"],
                                name="fk_rag_retrieval_candidates__chunk"),
        sa.ForeignKeyConstraint(["document_version_ref"],
                                ["plm.doc_document_versions.document_version_id"],
                                name="fk_rag_retrieval_candidates__document_version"),
        sa.ForeignKeyConstraint(["parse_result_ref"],
                                ["plm.doc_parse_result_refs.parse_result_ref_id"],
                                name="fk_rag_retrieval_candidates__parse_result"),
        sa.UniqueConstraint("retrieval_run_id", "candidate_ordinal",
                            name="uq_rag_retrieval_candidates__ordinal"),
        sa.UniqueConstraint("retrieval_run_id", "chunk_id",
                            name="uq_rag_retrieval_candidates__chunk"),
        sa.CheckConstraint(
            "(candidate_scope='GLOBAL' AND candidate_project_id IS NULL) OR "
            "(candidate_scope='PROJECT' AND candidate_project_id IS NOT NULL)",
            name="ck_rag_retrieval_candidates__scope_project"),
        sa.CheckConstraint(
            "source_type IN ('CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY',"
            "'REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER') AND "
            "jsonb_typeof(source_locator)='object' AND source_locator ? 'locator_type'",
            name="ck_rag_retrieval_candidates__source"),
        sa.CheckConstraint(
            "retrieval_channel IN ('FTS','VECTOR','HYBRID','EXACT') AND "
            "candidate_ordinal BETWEEN 0 AND 9999 AND "
            "final_score_micros BETWEEN -1000000000 AND 1000000000 AND "
            "octet_length(authorization_snapshot_fingerprint)=32 AND "
            "created_xid>0 AND isfinite(created_at)",
            name="ck_rag_retrieval_candidates__result"),
        schema="plm",
    )
    op.create_index("ix_rag_retrieval_candidates__run_rank",
                    "rag_retrieval_candidates",
                    ["retrieval_run_id", "candidate_ordinal"], schema="plm")
    op.create_table(
        "rag_retrieval_score_parts",
        sa.Column("score_part_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("retrieval_run_id", ident, nullable=False),
        sa.Column("project_id", ident),
        sa.Column("candidate_id", ident, nullable=False),
        sa.Column("score_kind", sa.Text(), nullable=False),
        sa.Column("score_ordinal", sa.Integer(), nullable=False),
        sa.Column("raw_score_micros", sa.BigInteger(), nullable=False),
        sa.Column("normalized_score_micros", sa.BigInteger(), nullable=False),
        sa.Column("weight_micros", sa.BigInteger(), nullable=False),
        sa.Column("weighted_score_micros", sa.BigInteger(), nullable=False),
        sa.Column("score_policy_ref", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["retrieval_run_id"],
                                ["plm.rag_retrieval_runs.retrieval_run_id"],
                                name="fk_rag_retrieval_score_parts__run"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_retrieval_score_parts__project"),
        sa.ForeignKeyConstraint(["candidate_id"],
                                ["plm.rag_retrieval_candidates.candidate_id"],
                                name="fk_rag_retrieval_score_parts__candidate"),
        sa.UniqueConstraint("candidate_id", "score_kind", "score_ordinal",
                            name="uq_rag_retrieval_score_parts__kind_ordinal"),
        sa.CheckConstraint(
            "score_kind IN ('FTS','VECTOR','METADATA','SOURCE_WEIGHT','RERANK','FINAL') "
            "AND score_ordinal BETWEEN 0 AND 31 AND "
            "raw_score_micros BETWEEN -1000000000 AND 1000000000 AND "
            "normalized_score_micros BETWEEN 0 AND 1000000 AND "
            "weight_micros BETWEEN 0 AND 1000000 AND "
            "weighted_score_micros BETWEEN -1000000000 AND 1000000000 AND "
            + _ref_check("score_policy_ref") + " AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_retrieval_score_parts__score"),
        schema="plm",
    )
    op.create_table(
        "rag_context_bundles",
        sa.Column("context_bundle_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("retrieval_run_id", ident, nullable=False),
        sa.Column("project_id", ident),
        sa.Column("context_policy_ref", sa.Text(), nullable=False),
        sa.Column("bundle_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("token_budget", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["retrieval_run_id"],
                                ["plm.rag_retrieval_runs.retrieval_run_id"],
                                name="fk_rag_context_bundles__run"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_context_bundles__project"),
        sa.UniqueConstraint("retrieval_run_id", "context_policy_ref",
                            name="uq_rag_context_bundles__run_policy"),
        sa.UniqueConstraint("bundle_fingerprint",
                            name="uq_rag_context_bundles__fingerprint"),
        sa.CheckConstraint(
            _ref_check("context_policy_ref") + " AND "
            "octet_length(bundle_fingerprint)=32 AND item_count BETWEEN 1 AND 100 AND "
            "token_budget BETWEEN 1 AND 1048576 AND token_count BETWEEN 1 AND token_budget "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_context_bundles__shape"),
        schema="plm",
    )
    op.create_table(
        "rag_context_items",
        sa.Column("context_item_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("context_bundle_id", ident, nullable=False),
        sa.Column("retrieval_run_id", ident, nullable=False),
        sa.Column("project_id", ident),
        sa.Column("candidate_id", ident, nullable=False),
        sa.Column("item_ordinal", sa.Integer(), nullable=False),
        sa.Column("chunk_id", ident, nullable=False),
        sa.Column("document_version_ref", ident, nullable=False),
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
        sa.Column("snippet_start", sa.Integer(), nullable=False),
        sa.Column("snippet_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("snippet_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("access_snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["context_bundle_id"],
                                ["plm.rag_context_bundles.context_bundle_id"],
                                name="fk_rag_context_items__bundle"),
        sa.ForeignKeyConstraint(["retrieval_run_id"],
                                ["plm.rag_retrieval_runs.retrieval_run_id"],
                                name="fk_rag_context_items__run"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_context_items__project"),
        sa.ForeignKeyConstraint(["candidate_id"],
                                ["plm.rag_retrieval_candidates.candidate_id"],
                                name="fk_rag_context_items__candidate"),
        sa.ForeignKeyConstraint(["chunk_id"], ["plm.rag_document_chunks.chunk_id"],
                                name="fk_rag_context_items__chunk"),
        sa.ForeignKeyConstraint(["document_version_ref"],
                                ["plm.doc_document_versions.document_version_id"],
                                name="fk_rag_context_items__document_version"),
        sa.UniqueConstraint("context_bundle_id", "item_ordinal",
                            name="uq_rag_context_items__ordinal"),
        sa.UniqueConstraint("context_bundle_id", "candidate_id",
                            name="uq_rag_context_items__candidate"),
        sa.CheckConstraint(
            "item_ordinal BETWEEN 0 AND 99 AND snippet_start>=0 AND "
            "snippet_end>snippet_start AND snippet_end-snippet_start<=8192 AND "
            "token_count BETWEEN 1 AND 16384 AND "
            "jsonb_typeof(source_locator)='object' AND source_locator ? 'locator_type' AND "
            "octet_length(snippet_fingerprint)=32 AND "
            "octet_length(access_snapshot_fingerprint)=32 AND "
            "created_xid>0 AND isfinite(created_at)",
            name="ck_rag_context_items__minimal"),
        schema="plm",
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Retrieval foundation downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.rag_context_items, plm.rag_context_bundles, "
        "plm.rag_retrieval_score_parts, plm.rag_retrieval_candidates, "
        "plm.rag_retrieval_query_contents, plm.rag_retrieval_runs "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_retrieval_runs)
               OR EXISTS (SELECT 1 FROM plm.rag_retrieval_query_contents)
               OR EXISTS (SELECT 1 FROM plm.rag_retrieval_candidates)
               OR EXISTS (SELECT 1 FROM plm.rag_retrieval_score_parts)
               OR EXISTS (SELECT 1 FROM plm.rag_context_bundles)
               OR EXISTS (SELECT 1 FROM plm.rag_context_items) THEN
                RAISE EXCEPTION 'RAG Retrieval history prevents downgrade';
            END IF;
        END $$;
    """)
    for table in (
        "rag_context_items", "rag_context_bundles", "rag_retrieval_score_parts",
        "rag_retrieval_candidates", "rag_retrieval_query_contents",
        "rag_retrieval_runs",
    ):
        op.drop_table(table, schema="plm")
    for name in (
        "guard_rag_retrieval_foundation_truncate", "guard_rag_context_item",
        "guard_rag_context_bundle", "guard_rag_retrieval_score_part",
        "guard_rag_retrieval_candidate", "validate_rag_retrieval_query_content",
        "guard_rag_retrieval_query_content", "guard_rag_retrieval_run_foundation",
    ):
        op.execute(f"DROP FUNCTION plm.{name}()")
