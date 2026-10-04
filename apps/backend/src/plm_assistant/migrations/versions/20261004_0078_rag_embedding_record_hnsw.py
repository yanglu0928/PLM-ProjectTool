"""Add immutable EmbeddingRecord and controlled HNSW dimension families.

Revision ID: 20261004_0078
Revises: 20261004_0077
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision = "20261004_0078"
down_revision = "20261004_0077"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_embedding_record()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    authorization_row plm.ai_egress_authorizations%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG EmbeddingRecord history is retained';
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO authorization_row FROM plm.ai_egress_authorizations
     WHERE authorization_id=NEW.egress_authorization_ref FOR KEY SHARE;
    IF index_row.embedding_index_id IS NULL
       OR index_row.index_state<>'BUILDING'
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id)
       OR NEW.embedding_model_ref<>index_row.embedding_model_ref
       OR NEW.embedding_dimension<>index_row.embedding_dimension
       OR NEW.embedding_state<>'AVAILABLE'
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG EmbeddingRecord Index binding is invalid or Build Owner is absent';
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

CREATE TRIGGER trg_rag_embedding_record_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_embedding_records
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_record();

CREATE FUNCTION plm.guard_rag_embedding_record_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RAG EmbeddingRecord history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_embedding_record_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_records
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_embedding_record_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_unique_constraint(
        "uq_rag_indexes__id_model_dimension",
        "rag_embedding_indexes",
        ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
        schema="plm",
    )
    op.create_unique_constraint(
        "uq_rag_index_sources__chunk_fingerprint",
        "rag_index_source_chunks",
        ["embedding_index_id", "chunk_id", "chunk_text_fingerprint"],
        schema="plm",
    )
    op.create_table(
        "rag_embedding_records",
        sa.Column("embedding_record_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("chunk_id", ident, nullable=False),
        sa.Column("embedding_model_ref", ident, nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("chunk_text_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("embedding_vector", Vector(), nullable=False),
        sa.Column("vector_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("embedding_state", sa.Text(), nullable=False,
                  server_default=sa.text("'AVAILABLE'")),
        sa.Column("provider_request_ref", sa.Text()),
        sa.Column("egress_authorization_ref", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_embeddings__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
            ["plm.rag_embedding_indexes.embedding_index_id",
             "plm.rag_embedding_indexes.embedding_model_ref",
             "plm.rag_embedding_indexes.embedding_dimension"],
            name="fk_rag_embeddings__index_model_dimension", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_index_id", "chunk_id", "chunk_text_fingerprint"],
            ["plm.rag_index_source_chunks.embedding_index_id",
             "plm.rag_index_source_chunks.chunk_id",
             "plm.rag_index_source_chunks.chunk_text_fingerprint"],
            name="fk_rag_embeddings__source_chunk", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["egress_authorization_ref"],
            ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_rag_embeddings__egress_authorization", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_embeddings__scope_project"),
        sa.CheckConstraint(
            "embedding_dimension IN (768,1024) "
            "AND vector_dims(embedding_vector)=embedding_dimension",
            name="ck_rag_embeddings__dimension"),
        sa.CheckConstraint(
            "octet_length(chunk_text_fingerprint)=32 "
            "AND octet_length(vector_fingerprint)=32",
            name="ck_rag_embeddings__fingerprints"),
        sa.CheckConstraint(
            "embedding_state IN ('AVAILABLE','FAILED','REVOKED') "
            "AND (provider_request_ref IS NULL OR "
            "(char_length(provider_request_ref) BETWEEN 1 AND 255 "
            "AND provider_request_ref !~ '[\\r\\n]')) "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_embeddings__state"),
        schema="plm",
    )
    op.create_index(
        "uq_rag_embeddings__index_chunk_available", "rag_embedding_records",
        ["embedding_index_id", "chunk_id"], unique=True, schema="plm",
        postgresql_where=sa.text("embedding_state='AVAILABLE'"),
    )
    op.create_index(
        "ix_rag_embeddings__project_index", "rag_embedding_records",
        ["project_id", "embedding_index_id", "embedding_record_id"], schema="plm",
    )
    op.execute(
        "CREATE INDEX ix_rag_embeddings__v768_hnsw "
        "ON plm.rag_embedding_records USING hnsw "
        "((embedding_vector::vector(768)) vector_cosine_ops) "
        "WITH (m=32,ef_construction=200) "
        "WHERE embedding_state='AVAILABLE' AND embedding_dimension=768"
    )
    op.execute(
        "CREATE INDEX ix_rag_embeddings__v1024_hnsw "
        "ON plm.rag_embedding_records USING hnsw "
        "((embedding_vector::vector(1024)) vector_cosine_ops) "
        "WITH (m=32,ef_construction=200) "
        "WHERE embedding_state='AVAILABLE' AND embedding_dimension=1024"
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG EmbeddingRecord downgrade is disabled")
    op.execute("LOCK TABLE plm.rag_embedding_records, "
               "plm.rag_index_source_chunks, plm.rag_embedding_indexes "
               "IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_records) THEN
                RAISE EXCEPTION 'RAG EmbeddingRecord history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_embedding_record_no_truncate "
               "ON plm.rag_embedding_records")
    op.execute("DROP TRIGGER trg_rag_embedding_record_guard "
               "ON plm.rag_embedding_records")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_record_truncate()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_record()")
    op.execute("DROP INDEX plm.ix_rag_embeddings__v1024_hnsw")
    op.execute("DROP INDEX plm.ix_rag_embeddings__v768_hnsw")
    op.drop_index("ix_rag_embeddings__project_index",
                  table_name="rag_embedding_records", schema="plm")
    op.drop_index("uq_rag_embeddings__index_chunk_available",
                  table_name="rag_embedding_records", schema="plm")
    op.drop_table("rag_embedding_records", schema="plm")
    op.drop_constraint(
        "uq_rag_index_sources__chunk_fingerprint", "rag_index_source_chunks",
        schema="plm", type_="unique",
    )
    op.drop_constraint(
        "uq_rag_indexes__id_model_dimension", "rag_embedding_indexes",
        schema="plm", type_="unique",
    )
