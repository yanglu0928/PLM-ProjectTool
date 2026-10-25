"""Add sealed Embedding build roots and individually authorized batches.

Revision ID: 20261004_0079
Revises: 20261004_0078
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261004_0079"
down_revision = "20261004_0078"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_embedding_build()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
    expected_payload jsonb;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild history is retained until Build Owner transitions are installed';
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO job_row FROM plm.job_jobs
     WHERE job_id=NEW.build_job_ref FOR KEY SHARE;
    expected_payload := jsonb_build_object(
        'embedding_build_id',NEW.embedding_build_id::text,
        'embedding_index_id',NEW.embedding_index_id::text,
        'build_generation',NEW.build_generation);
    IF index_row.embedding_index_id IS NULL OR index_row.index_state<>'PLANNED'
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id)
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
       OR ROW(job_row.scope,job_row.project_id) IS DISTINCT FROM
          ROW(NEW.scope,NEW.project_id)
       OR job_row.actor_ref IS DISTINCT FROM NEW.created_by
       OR job_row.payload_refs<>expected_payload
       OR job_row.state<>'PENDING' OR job_row.max_attempts<>1
       OR job_row.attempt_count<>0 OR job_row.fencing_token<>0 THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild unique Job Owner binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_embedding_build_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_embedding_builds
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_build();

CREATE FUNCTION plm.guard_rag_embedding_build_batch()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    build_row plm.rag_embedding_builds%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG EmbeddingBuildBatch history is retained until Worker transitions are installed';
    END IF;
    SELECT * INTO build_row FROM plm.rag_embedding_builds
     WHERE embedding_build_id=NEW.embedding_build_id FOR KEY SHARE;
    IF build_row.embedding_build_id IS NULL OR build_row.build_state<>'PLANNED'
       OR build_row.created_xid<>txid_current()
       OR NEW.created_xid<>build_row.created_xid
       OR NEW.batch_state<>'PENDING' OR NEW.lock_version<>0
       OR NEW.send_fencing_token IS NOT NULL
       OR NEW.provider_request_ref IS NOT NULL OR NEW.error_code IS NOT NULL
       OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL THEN
        RAISE EXCEPTION 'RAG EmbeddingBuildBatch initial state is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_embedding_build_batch_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_embedding_build_batches
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_build_batch();

CREATE FUNCTION plm.validate_rag_embedding_build_plan()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    actual_batch_count bigint;
    maximum_batch_ordinal bigint;
    actual_record_count bigint;
    ranges_are_contiguous boolean;
    authorization_fingerprint bytea;
    expected_build_fingerprint bytea;
BEGIN
    SELECT count(*),max(batch_ordinal),sum(source_record_count),
           bool_and(source_first_ordinal=expected_first)
      INTO actual_batch_count,maximum_batch_ordinal,actual_record_count,
           ranges_are_contiguous
      FROM (
        SELECT batch_ordinal,source_first_ordinal,source_record_count,
               1+coalesce(sum(source_record_count) OVER (
                   ORDER BY batch_ordinal ROWS BETWEEN UNBOUNDED PRECEDING
                   AND 1 PRECEDING),0) AS expected_first
          FROM plm.rag_embedding_build_batches
         WHERE embedding_build_id=NEW.embedding_build_id
      ) batch_ranges;
    IF actual_batch_count<>NEW.batch_count
       OR maximum_batch_ordinal<>NEW.batch_count
       OR actual_record_count<>NEW.source_chunk_count
       OR ranges_are_contiguous IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild batch partition is incomplete';
    END IF;
    IF EXISTS (
        SELECT 1 FROM plm.rag_embedding_build_batches batch
         WHERE batch.embedding_build_id=NEW.embedding_build_id
           AND batch.source_batch_fingerprint IS DISTINCT FROM (
               SELECT sha256(convert_to(string_agg(
                   source.source_ordinal::text || ':' || source.chunk_id::text || ':' ||
                   encode(source.chunk_text_fingerprint,'hex'), E'\n'
                   ORDER BY source.source_ordinal), 'UTF8'))
                 FROM plm.rag_index_source_chunks source
                WHERE source.embedding_index_id=NEW.embedding_index_id
                  AND source.source_ordinal BETWEEN batch.source_first_ordinal
                      AND batch.source_first_ordinal+batch.source_record_count-1)) THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild batch source fingerprint is invalid';
    END IF;
    IF EXISTS (
        SELECT 1 FROM plm.rag_embedding_build_batches batch
        JOIN plm.ai_egress_authorizations authz
          ON authz.authorization_id=batch.egress_authorization_ref
       WHERE batch.embedding_build_id=NEW.embedding_build_id
         AND (ROW(authz.scope,authz.project_id) IS DISTINCT FROM
              ROW(NEW.scope,NEW.project_id)
          OR authz.ai_model_id<>NEW.embedding_model_ref
          OR authz.operation_type NOT IN ('INDEX_BUILD','INDEX_REBUILD')
          OR authz.authorization_state<>'AUTHORIZED'
          OR authz.valid_until<=NEW.created_at
          OR authz.max_retry_attempts<>1
          OR authz.max_record_count<batch.source_record_count
          OR authz.max_payload_bytes<batch.payload_bytes
          OR authz.max_input_tokens<batch.input_tokens
          OR authz.payload_fingerprint<>batch.payload_fingerprint
          OR authz.source_refs_fingerprint<>batch.source_batch_fingerprint
          OR EXISTS (
              SELECT 1 FROM plm.rag_index_source_chunks source
              JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
             WHERE source.embedding_index_id=NEW.embedding_index_id
               AND source.source_ordinal BETWEEN batch.source_first_ordinal
                   AND batch.source_first_ordinal+batch.source_record_count-1
               AND NOT authz.allowed_data_categories ? chunk.source_type))) THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild batch authorization is invalid';
    END IF;
    SELECT sha256(convert_to(string_agg(
               batch_ordinal::text || ':' || egress_authorization_ref::text || ':' ||
               encode(source_batch_fingerprint,'hex') || ':' ||
               encode(payload_fingerprint,'hex'), E'\n' ORDER BY batch_ordinal), 'UTF8'))
      INTO authorization_fingerprint
      FROM plm.rag_embedding_build_batches
     WHERE embedding_build_id=NEW.embedding_build_id;
    IF authorization_fingerprint IS DISTINCT FROM NEW.authorization_set_fingerprint THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild authorization set fingerprint is invalid';
    END IF;
    expected_build_fingerprint := sha256(convert_to(
        NEW.embedding_index_id::text || ':' || NEW.build_generation::text || ':' ||
        encode(NEW.source_snapshot_fingerprint,'hex') || ':' ||
        encode(NEW.authorization_set_fingerprint,'hex') || ':' ||
        NEW.batch_count::text, 'UTF8'));
    IF expected_build_fingerprint IS DISTINCT FROM NEW.build_fingerprint THEN
        RAISE EXCEPTION 'RAG EmbeddingBuild fingerprint is invalid';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_embedding_build_plan_complete
AFTER INSERT ON plm.rag_embedding_builds
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_rag_embedding_build_plan();

CREATE FUNCTION plm.guard_rag_embedding_build_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RAG Embedding build history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_embedding_build_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_builds
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_embedding_build_truncate();

CREATE TRIGGER trg_rag_embedding_build_batch_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_build_batches
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_embedding_build_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "rag_embedding_builds",
        sa.Column("embedding_build_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("embedding_model_ref", ident, nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("build_generation", sa.BigInteger(), nullable=False),
        sa.Column("build_job_ref", ident, nullable=False),
        sa.Column("source_chunk_count", sa.BigInteger(), nullable=False),
        sa.Column("source_snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("batch_count", sa.Integer(), nullable=False),
        sa.Column("authorization_set_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("build_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("build_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PLANNED'")),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_rag_builds__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
            ["plm.rag_embedding_indexes.embedding_index_id",
             "plm.rag_embedding_indexes.embedding_model_ref",
             "plm.rag_embedding_indexes.embedding_dimension"],
            name="fk_rag_builds__index_model_dimension", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["build_job_ref"], ["plm.job_jobs.job_id"],
                                name="fk_rag_builds__job", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_rag_builds__creator", ondelete="NO ACTION"),
        sa.UniqueConstraint("embedding_index_id", name="uq_rag_builds__index"),
        sa.UniqueConstraint("build_job_ref", name="uq_rag_builds__job"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_builds__scope_project"),
        sa.CheckConstraint(
            "build_generation BETWEEN 1 AND 9223372036854775807 "
            "AND embedding_dimension IN (768,1024) "
            "AND source_chunk_count BETWEEN 1 AND 1000000000 "
            "AND batch_count BETWEEN 1 AND 100000",
            name="ck_rag_builds__counts"),
        sa.CheckConstraint(
            "octet_length(source_snapshot_fingerprint)=32 "
            "AND octet_length(authorization_set_fingerprint)=32 "
            "AND octet_length(build_fingerprint)=32",
            name="ck_rag_builds__fingerprints"),
        sa.CheckConstraint(
            "build_state IN ('PLANNED','RUNNING','SUCCEEDED','FAILED','UNKNOWN','CANCELLED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_builds__state"),
        schema="plm",
    )
    op.create_index(
        "ix_rag_builds__project_state", "rag_embedding_builds",
        ["project_id", "build_state", "embedding_build_id"], schema="plm",
    )
    op.create_table(
        "rag_embedding_build_batches",
        sa.Column("embedding_build_batch_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("embedding_build_id", ident, nullable=False),
        sa.Column("batch_ordinal", sa.Integer(), nullable=False),
        sa.Column("source_first_ordinal", sa.BigInteger(), nullable=False),
        sa.Column("source_record_count", sa.Integer(), nullable=False),
        sa.Column("source_batch_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("payload_bytes", sa.BigInteger(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("egress_authorization_ref", ident, nullable=False),
        sa.Column("batch_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("send_fencing_token", sa.BigInteger()),
        sa.Column("provider_request_ref", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("started_at", timestamp),
        sa.Column("completed_at", timestamp),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["embedding_build_id"], ["plm.rag_embedding_builds.embedding_build_id"],
            name="fk_rag_build_batches__build", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["egress_authorization_ref"],
            ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_rag_build_batches__authorization", ondelete="NO ACTION"),
        sa.UniqueConstraint("embedding_build_id", "batch_ordinal",
                            name="uq_rag_build_batches__ordinal"),
        sa.UniqueConstraint("embedding_build_id", "source_first_ordinal",
                            name="uq_rag_build_batches__source_start"),
        sa.UniqueConstraint("egress_authorization_ref",
                            name="uq_rag_build_batches__authorization"),
        sa.CheckConstraint(
            "batch_ordinal BETWEEN 1 AND 100000 "
            "AND source_first_ordinal BETWEEN 1 AND 1000000000 "
            "AND source_record_count BETWEEN 1 AND 1000 "
            "AND payload_bytes BETWEEN 1 AND 100000000 "
            "AND input_tokens BETWEEN 1 AND 1048576",
            name="ck_rag_build_batches__bounds"),
        sa.CheckConstraint(
            "octet_length(source_batch_fingerprint)=32 "
            "AND octet_length(payload_fingerprint)=32",
            name="ck_rag_build_batches__fingerprints"),
        sa.CheckConstraint(
            "batch_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','UNKNOWN','CANCELLED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_build_batches__state"),
        sa.CheckConstraint(
            "(batch_state='PENDING' AND send_fencing_token IS NULL "
            "AND provider_request_ref IS NULL AND error_code IS NULL "
            "AND started_at IS NULL AND completed_at IS NULL) OR "
            "(batch_state='RUNNING' AND send_fencing_token>0 "
            "AND error_code IS NULL AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(batch_state='SUCCEEDED' AND send_fencing_token>0 "
            "AND error_code IS NULL AND started_at IS NOT NULL "
            "AND completed_at>=started_at) OR "
            "(batch_state IN ('FAILED','UNKNOWN','CANCELLED') "
            "AND error_code IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at>=started_at)",
            name="ck_rag_build_batches__lifecycle"),
        sa.CheckConstraint(
            "(provider_request_ref IS NULL OR "
            "(char_length(provider_request_ref) BETWEEN 1 AND 255 "
            "AND provider_request_ref !~ '[\\r\\n]')) "
            "AND (error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_rag_build_batches__result"),
        schema="plm",
    )
    op.create_index(
        "ix_rag_build_batches__build_state", "rag_embedding_build_batches",
        ["embedding_build_id", "batch_state", "batch_ordinal"], schema="plm",
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG EmbeddingBuild downgrade is disabled")
    op.execute("LOCK TABLE plm.rag_embedding_build_batches, "
               "plm.rag_embedding_builds IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_builds)
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_build_batches) THEN
                RAISE EXCEPTION 'RAG EmbeddingBuild history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_embedding_build_batch_no_truncate "
               "ON plm.rag_embedding_build_batches")
    op.execute("DROP TRIGGER trg_rag_embedding_build_no_truncate "
               "ON plm.rag_embedding_builds")
    op.execute("DROP TRIGGER trg_rag_embedding_build_plan_complete "
               "ON plm.rag_embedding_builds")
    op.execute("DROP TRIGGER trg_rag_embedding_build_batch_guard "
               "ON plm.rag_embedding_build_batches")
    op.execute("DROP TRIGGER trg_rag_embedding_build_guard "
               "ON plm.rag_embedding_builds")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_build_truncate()")
    op.execute("DROP FUNCTION plm.validate_rag_embedding_build_plan()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_build_batch()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_build()")
    op.drop_index("ix_rag_build_batches__build_state",
                  table_name="rag_embedding_build_batches", schema="plm")
    op.drop_table("rag_embedding_build_batches", schema="plm")
    op.drop_index("ix_rag_builds__project_state",
                  table_name="rag_embedding_builds", schema="plm")
    op.drop_table("rag_embedding_builds", schema="plm")
