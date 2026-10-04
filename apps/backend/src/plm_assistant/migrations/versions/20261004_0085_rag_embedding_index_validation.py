"""Add immutable technical validation evidence for an EmbeddingIndex build.

Revision ID: 20261004_0085
Revises: 20261004_0084
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261004_0085"
down_revision = "20261004_0084"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_embedding_index_validation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    build_row plm.rag_embedding_builds%ROWTYPE;
    job_row plm.job_jobs%ROWTYPE;
    lease_row plm.job_leases%ROWTYPE;
    actual_source_count bigint;
    actual_available_count bigint;
    actual_missing_count bigint;
    actual_extra_count bigint;
    actual_duplicate_count bigint;
    actual_invalid_count bigint;
    actual_batch_count bigint;
    actual_succeeded_batch_count bigint;
    actual_record_set_fingerprint bytea;
    expected_hnsw_index_name text;
    actual_hnsw_definition text;
    actual_hnsw_catalog_fingerprint bytea;
    expected_observed_recall integer;
    expected_validation_fingerprint bytea;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation history is immutable';
    END IF;
    NEW.completed_at := statement_timestamp();
    NEW.created_xid := txid_current();

    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO build_row FROM plm.rag_embedding_builds
     WHERE embedding_build_id=NEW.embedding_build_id FOR KEY SHARE;
    IF index_row.embedding_index_id IS NULL
       OR build_row.embedding_build_id IS NULL
       OR build_row.embedding_index_id<>NEW.embedding_index_id
       OR index_row.index_state<>'BUILDING'
       OR build_row.build_state<>'RUNNING'
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id)
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(build_row.scope,build_row.project_id)
       OR NEW.embedding_model_ref<>index_row.embedding_model_ref
       OR NEW.embedding_model_ref<>build_row.embedding_model_ref
       OR NEW.embedding_dimension<>index_row.embedding_dimension
       OR NEW.embedding_dimension<>build_row.embedding_dimension
       OR NEW.source_chunk_count<>index_row.source_chunk_count
       OR NEW.source_chunk_count<>build_row.source_chunk_count
       OR NEW.source_snapshot_fingerprint<>index_row.source_snapshot_fingerprint
       OR NEW.source_snapshot_fingerprint<>build_row.source_snapshot_fingerprint
       OR NEW.build_fingerprint<>build_row.build_fingerprint
       OR NEW.expected_batch_count<>build_row.batch_count THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation build binding is invalid';
    END IF;

    SELECT * INTO job_row FROM plm.job_jobs
     WHERE job_id=build_row.build_job_ref FOR KEY SHARE;
    SELECT * INTO lease_row FROM plm.job_leases
     WHERE job_id=build_row.build_job_ref AND state='ACTIVE' FOR KEY SHARE;
    IF job_row.job_id IS NULL OR job_row.owner_module<>'rag'
       OR job_row.job_type<>'RAG_INDEX_BUILD'
       OR job_row.state<>'RUNNING' OR job_row.max_attempts<>1
       OR job_row.attempt_count<>1 OR job_row.fencing_token<>1
       OR lease_row.lease_id IS NULL OR lease_row.fencing_token<>1
       OR lease_row.lease_expires_at<=clock_timestamp()
       OR lease_row.worker_ref IS NULL THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation current lease is invalid';
    END IF;

    SELECT count(*) INTO actual_source_count
      FROM plm.rag_index_source_chunks source
     WHERE source.embedding_index_id=NEW.embedding_index_id;
    SELECT count(*) FILTER (WHERE record.embedding_state='AVAILABLE'),
           count(*) FILTER (WHERE record.embedding_state<>'AVAILABLE')
      INTO actual_available_count,actual_invalid_count
      FROM plm.rag_embedding_records record
     WHERE record.embedding_index_id=NEW.embedding_index_id;
    SELECT count(*) INTO actual_missing_count
      FROM plm.rag_index_source_chunks source
     WHERE source.embedding_index_id=NEW.embedding_index_id
       AND NOT EXISTS (
           SELECT 1 FROM plm.rag_embedding_records record
            WHERE record.embedding_index_id=source.embedding_index_id
              AND record.chunk_id=source.chunk_id
              AND record.embedding_state='AVAILABLE');
    SELECT count(*) INTO actual_extra_count
      FROM plm.rag_embedding_records record
     WHERE record.embedding_index_id=NEW.embedding_index_id
       AND record.embedding_state='AVAILABLE'
       AND NOT EXISTS (
           SELECT 1 FROM plm.rag_index_source_chunks source
            WHERE source.embedding_index_id=record.embedding_index_id
              AND source.chunk_id=record.chunk_id);
    SELECT coalesce(sum(duplicates-1),0) INTO actual_duplicate_count
      FROM (
        SELECT count(*) AS duplicates
          FROM plm.rag_embedding_records record
         WHERE record.embedding_index_id=NEW.embedding_index_id
           AND record.embedding_state='AVAILABLE'
         GROUP BY record.chunk_id HAVING count(*)>1
      ) duplicate_groups;
    SELECT count(*),count(*) FILTER (WHERE batch_state='SUCCEEDED')
      INTO actual_batch_count,actual_succeeded_batch_count
      FROM plm.rag_embedding_build_batches batch
     WHERE batch.embedding_build_id=NEW.embedding_build_id;
    SELECT sha256(convert_to(coalesce(string_agg(
               source.source_ordinal::text || ':' || record.chunk_id::text || ':' ||
               encode(record.vector_fingerprint,'hex'), E'\n'
               ORDER BY source.source_ordinal), ''), 'UTF8'))
      INTO actual_record_set_fingerprint
      FROM plm.rag_index_source_chunks source
      JOIN plm.rag_embedding_records record
        ON record.embedding_index_id=source.embedding_index_id
       AND record.chunk_id=source.chunk_id
       AND record.embedding_state='AVAILABLE'
     WHERE source.embedding_index_id=NEW.embedding_index_id;

    IF NEW.source_chunk_count<>actual_source_count
       OR NEW.available_record_count<>actual_available_count
       OR NEW.missing_record_count<>actual_missing_count
       OR NEW.extra_record_count<>actual_extra_count
       OR NEW.duplicate_record_count<>actual_duplicate_count
       OR NEW.invalid_record_count<>actual_invalid_count
       OR NEW.expected_batch_count<>actual_batch_count
       OR NEW.succeeded_batch_count<>actual_succeeded_batch_count
       OR NEW.record_set_fingerprint IS DISTINCT FROM
          actual_record_set_fingerprint THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation observed facts are invalid';
    END IF;

    expected_hnsw_index_name :=
        'ix_rag_embeddings__v' || NEW.embedding_dimension::text || '_hnsw';
    SELECT indexdef INTO actual_hnsw_definition
      FROM pg_indexes WHERE schemaname='plm'
       AND tablename='rag_embedding_records'
       AND indexname=expected_hnsw_index_name;
    IF actual_hnsw_definition IS NOT NULL THEN
        actual_hnsw_catalog_fingerprint :=
            sha256(convert_to(actual_hnsw_definition,'UTF8'));
    END IF;
    IF NEW.hnsw_index_name<>expected_hnsw_index_name
       OR NEW.hnsw_catalog_fingerprint IS DISTINCT FROM
          actual_hnsw_catalog_fingerprint THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation HNSW catalog is invalid';
    END IF;

    expected_observed_recall := CASE
        WHEN NEW.exact_expected_count=0 THEN 0
        ELSE floor(NEW.exact_overlap_count*10000.0/
                   NEW.exact_expected_count)::integer
    END;
    IF NEW.observed_recall_basis_points<>expected_observed_recall THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation recall summary is invalid';
    END IF;
    expected_validation_fingerprint := sha256(
        convert_to('rag-index-technical-v1','UTF8') || decode('00','hex') ||
        actual_record_set_fingerprint ||
        coalesce(actual_hnsw_catalog_fingerprint,decode('','hex')) ||
        coalesce(NEW.plan_fingerprint,decode('','hex'))
    );
    IF NEW.validation_fingerprint<>expected_validation_fingerprint THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation fingerprint is invalid';
    END IF;

    IF NEW.validation_state='PASSED'
       AND (actual_source_count<>actual_available_count
            OR actual_missing_count<>0 OR actual_extra_count<>0
            OR actual_duplicate_count<>0 OR actual_invalid_count<>0
            OR actual_batch_count<>actual_succeeded_batch_count) THEN
        RAISE EXCEPTION 'RAG EmbeddingIndexValidation cannot pass incomplete history';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_embedding_index_validation_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_embedding_index_validations
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_index_validation();

CREATE FUNCTION plm.guard_rag_embedding_index_validation_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RAG EmbeddingIndexValidation history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_embedding_index_validation_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_index_validations
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_embedding_index_validation_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "rag_embedding_index_validations",
        sa.Column("embedding_index_validation_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("embedding_build_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("embedding_model_ref", ident, nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("source_chunk_count", sa.BigInteger(), nullable=False),
        sa.Column("available_record_count", sa.BigInteger(), nullable=False),
        sa.Column("missing_record_count", sa.BigInteger(), nullable=False),
        sa.Column("extra_record_count", sa.BigInteger(), nullable=False),
        sa.Column("duplicate_record_count", sa.BigInteger(), nullable=False),
        sa.Column("invalid_record_count", sa.BigInteger(), nullable=False),
        sa.Column("expected_batch_count", sa.Integer(), nullable=False),
        sa.Column("succeeded_batch_count", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("build_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("record_set_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("validation_policy_ref", sa.Text(), nullable=False),
        sa.Column("hnsw_index_name", sa.Text(), nullable=False),
        sa.Column("hnsw_catalog_fingerprint", sa.LargeBinary()),
        sa.Column("hnsw_plan_observed", sa.Boolean(), nullable=False),
        sa.Column("exact_plan_observed", sa.Boolean(), nullable=False),
        sa.Column("hnsw_ef_search", sa.Integer(), nullable=False),
        sa.Column("hnsw_iterative_scan", sa.Text(), nullable=False),
        sa.Column("exact_query_count", sa.Integer(), nullable=False),
        sa.Column("exact_top_k", sa.Integer(), nullable=False),
        sa.Column("exact_overlap_count", sa.BigInteger(), nullable=False),
        sa.Column("exact_expected_count", sa.BigInteger(), nullable=False),
        sa.Column("minimum_recall_basis_points", sa.Integer(), nullable=False),
        sa.Column("observed_recall_basis_points", sa.Integer(), nullable=False),
        sa.Column("plan_fingerprint", sa.LargeBinary()),
        sa.Column("validation_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("validation_state", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("validated_by", ident, nullable=False),
        sa.Column("completed_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_validations__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
            ["plm.rag_embedding_indexes.embedding_index_id",
             "plm.rag_embedding_indexes.embedding_model_ref",
             "plm.rag_embedding_indexes.embedding_dimension"],
            name="fk_rag_index_validations__index_model_dimension",
            ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_build_id"], ["plm.rag_embedding_builds.embedding_build_id"],
            name="fk_rag_index_validations__build", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["validated_by"], ["plm.auth_users.user_id"],
            name="fk_rag_index_validations__validator", ondelete="NO ACTION"),
        sa.UniqueConstraint(
            "embedding_index_id", name="uq_rag_index_validations__index"),
        sa.UniqueConstraint(
            "embedding_build_id", name="uq_rag_index_validations__build"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_validations__scope_project"),
        sa.CheckConstraint(
            "embedding_dimension IN (768,1024) "
            "AND source_chunk_count BETWEEN 1 AND 1000000000 "
            "AND available_record_count BETWEEN 0 AND 1000000000 "
            "AND missing_record_count BETWEEN 0 AND 1000000000 "
            "AND extra_record_count BETWEEN 0 AND 1000000000 "
            "AND duplicate_record_count BETWEEN 0 AND 1000000000 "
            "AND invalid_record_count BETWEEN 0 AND 1000000000 "
            "AND expected_batch_count BETWEEN 1 AND 100000 "
            "AND succeeded_batch_count BETWEEN 0 AND 100000",
            name="ck_rag_index_validations__counts"),
        sa.CheckConstraint(
            "octet_length(source_snapshot_fingerprint)=32 "
            "AND octet_length(build_fingerprint)=32 "
            "AND octet_length(record_set_fingerprint)=32 "
            "AND octet_length(validation_fingerprint)=32 "
            "AND (hnsw_catalog_fingerprint IS NULL OR "
            "octet_length(hnsw_catalog_fingerprint)=32) "
            "AND (plan_fingerprint IS NULL OR octet_length(plan_fingerprint)=32)",
            name="ck_rag_index_validations__fingerprints"),
        sa.CheckConstraint(
            "validation_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND hnsw_index_name ~ '^ix_rag_embeddings__v(768|1024)_hnsw$' "
            "AND exact_query_count BETWEEN 0 AND 10000 "
            "AND exact_top_k BETWEEN 0 AND 1000 "
            "AND exact_overlap_count BETWEEN 0 AND 10000000 "
            "AND exact_expected_count BETWEEN 0 AND 10000000 "
            "AND exact_overlap_count<=exact_expected_count "
            "AND exact_expected_count<=exact_query_count*exact_top_k "
            "AND hnsw_ef_search BETWEEN 1 AND 1000 "
            "AND hnsw_iterative_scan IN ('off','strict_order','relaxed_order') "
            "AND minimum_recall_basis_points BETWEEN 1 AND 10000 "
            "AND observed_recall_basis_points BETWEEN 0 AND 10000",
            name="ck_rag_index_validations__probe"),
        sa.CheckConstraint(
            "(validation_state='PASSED' AND error_code IS NULL "
            "AND available_record_count=source_chunk_count "
            "AND missing_record_count=0 AND extra_record_count=0 "
            "AND duplicate_record_count=0 AND invalid_record_count=0 "
            "AND succeeded_batch_count=expected_batch_count "
            "AND hnsw_catalog_fingerprint IS NOT NULL "
            "AND hnsw_plan_observed AND exact_plan_observed "
            "AND hnsw_ef_search=200 AND hnsw_iterative_scan='strict_order' "
            "AND exact_query_count>0 AND exact_top_k>0 "
            "AND exact_expected_count>0 AND plan_fingerprint IS NOT NULL "
            "AND observed_recall_basis_points>=minimum_recall_basis_points) OR "
            "(validation_state='FAILED' "
            "AND error_code ~ '^RAG_[A-Z0-9_]{1,59}$')",
            name="ck_rag_index_validations__result"),
        sa.CheckConstraint(
            "created_xid>0 AND isfinite(completed_at)",
            name="ck_rag_index_validations__history"),
        schema="plm",
    )
    op.create_index(
        "ix_rag_index_validations__project_result",
        "rag_embedding_index_validations",
        ["project_id", "validation_state", "completed_at",
         "embedding_index_validation_id"],
        schema="plm",
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG EmbeddingIndexValidation downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.rag_embedding_index_validations "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_index_validations) THEN
                RAISE EXCEPTION
                    'RAG EmbeddingIndexValidation history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute(
        "DROP TRIGGER trg_rag_embedding_index_validation_no_truncate "
        "ON plm.rag_embedding_index_validations"
    )
    op.execute(
        "DROP TRIGGER trg_rag_embedding_index_validation_guard "
        "ON plm.rag_embedding_index_validations"
    )
    op.execute("DROP FUNCTION plm.guard_rag_embedding_index_validation_truncate()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_index_validation()")
    op.drop_index(
        "ix_rag_index_validations__project_result",
        table_name="rag_embedding_index_validations", schema="plm",
    )
    op.drop_table("rag_embedding_index_validations", schema="plm")
