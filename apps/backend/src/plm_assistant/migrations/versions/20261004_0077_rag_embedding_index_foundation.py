"""Add planned EmbeddingIndex identities and exact Chunk snapshots.

Revision ID: 20261004_0077
Revises: 20261004_0076
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261004_0077"
down_revision = "20261004_0076"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_embedding_index()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    model_kind text;
    model_dimension integer;
    model_state text;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'RAG EmbeddingIndex history is retained';
    END IF;
    IF TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'RAG EmbeddingIndex state changes are closed until build ownership is installed';
    END IF;
    IF NEW.index_state<>'PLANNED' OR NEW.lock_version<>0
       OR NEW.created_xid<>txid_current() THEN
        RAISE EXCEPTION 'RAG EmbeddingIndex must start PLANNED in its creation transaction';
    END IF;
    SELECT model.model_kind,model.embedding_dimension,model.model_state
      INTO model_kind,model_dimension,model_state
      FROM plm.ai_models model
     WHERE model.ai_model_id=NEW.embedding_model_ref
     FOR KEY SHARE;
    IF model_kind IS DISTINCT FROM 'EMBEDDING'
       OR model_dimension IS DISTINCT FROM NEW.embedding_dimension
       OR model_state IS DISTINCT FROM 'AVAILABLE' THEN
        RAISE EXCEPTION 'RAG EmbeddingIndex model binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_embedding_index_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_embedding_indexes
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_index();

CREATE FUNCTION plm.guard_rag_index_source_chunk()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    chunk_row plm.rag_document_chunks%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Index source snapshot history is retained';
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO chunk_row FROM plm.rag_document_chunks
     WHERE chunk_id=NEW.chunk_id FOR KEY SHARE;
    IF index_row.embedding_index_id IS NULL OR chunk_row.chunk_id IS NULL
       OR index_row.index_state<>'PLANNED'
       OR index_row.created_xid<>txid_current()
       OR NEW.created_xid<>index_row.created_xid
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id)
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(chunk_row.scope,chunk_row.project_id)
       OR ROW(index_row.chunk_profile,index_row.chunk_profile_version)
          IS DISTINCT FROM
          ROW(chunk_row.chunk_profile,chunk_row.chunk_profile_version)
       OR chunk_row.chunk_state<>'ACTIVE'
       OR NEW.chunk_text_fingerprint IS DISTINCT FROM chunk_row.text_fingerprint THEN
        RAISE EXCEPTION 'RAG Index source Chunk binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_index_source_chunk_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_index_source_chunks
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_index_source_chunk();

CREATE FUNCTION plm.validate_rag_index_source_snapshot()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    actual_count bigint;
    maximum_ordinal bigint;
    actual_fingerprint bytea;
BEGIN
    SELECT count(*),max(source_ordinal),
           sha256(convert_to(string_agg(
               source_ordinal::text || ':' || chunk_id::text || ':' ||
               encode(chunk_text_fingerprint,'hex'), E'\n'
               ORDER BY source_ordinal), 'UTF8'))
      INTO actual_count,maximum_ordinal,actual_fingerprint
      FROM plm.rag_index_source_chunks
     WHERE embedding_index_id=NEW.embedding_index_id;
    IF actual_count<>NEW.source_chunk_count
       OR maximum_ordinal<>NEW.source_chunk_count
       OR actual_fingerprint IS DISTINCT FROM NEW.source_snapshot_fingerprint THEN
        RAISE EXCEPTION 'RAG Index source snapshot count or fingerprint is invalid';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_index_source_snapshot_complete
AFTER INSERT ON plm.rag_embedding_indexes
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_rag_index_source_snapshot();

CREATE FUNCTION plm.guard_rag_index_foundation_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RAG Index foundation history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_embedding_index_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_indexes
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_index_foundation_truncate();

CREATE TRIGGER trg_rag_index_source_chunk_no_truncate
BEFORE TRUNCATE ON plm.rag_index_source_chunks
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_index_foundation_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "rag_embedding_indexes",
        sa.Column("embedding_index_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("index_purpose", sa.Text(), nullable=False),
        sa.Column("embedding_model_ref", ident, nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("chunk_profile", sa.Text(), nullable=False),
        sa.Column("chunk_profile_version", sa.Integer(), nullable=False),
        sa.Column("source_chunk_count", sa.BigInteger(), nullable=False),
        sa.Column("source_snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("index_version", sa.BigInteger(), nullable=False),
        sa.Column("index_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PLANNED'")),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_indexes__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_model_ref"], ["plm.ai_models.ai_model_id"],
            name="fk_rag_indexes__model", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_rag_indexes__creator", ondelete="NO ACTION"),
        sa.UniqueConstraint(
            "scope", "project_id", "index_purpose", "index_version",
            name="uq_rag_indexes__purpose_version",
            postgresql_nulls_not_distinct=True),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_indexes__scope_project"),
        sa.CheckConstraint(
            "index_purpose ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND chunk_profile ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_rag_indexes__refs"),
        sa.CheckConstraint(
            "embedding_dimension BETWEEN 1 AND 2000 "
            "AND chunk_profile_version BETWEEN 1 AND 2147483647 "
            "AND index_version BETWEEN 1 AND 9223372036854775807",
            name="ck_rag_indexes__versions"),
        sa.CheckConstraint(
            "source_chunk_count BETWEEN 1 AND 1000000000 "
            "AND octet_length(source_snapshot_fingerprint)=32",
            name="ck_rag_indexes__snapshot"),
        sa.CheckConstraint(
            "index_state IN ('PLANNED','BUILDING','READY','ACTIVE','FAILED','RETIRED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_indexes__state"),
        schema="plm",
    )
    op.create_index(
        "uq_rag_indexes__active_purpose", "rag_embedding_indexes",
        ["scope", "project_id", "index_purpose"], unique=True,
        schema="plm", postgresql_where=sa.text("index_state='ACTIVE'"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_index(
        "ix_rag_indexes__project_purpose_version", "rag_embedding_indexes",
        ["project_id", "index_purpose", sa.text("index_version DESC"),
         "embedding_index_id"], schema="plm",
    )
    op.create_table(
        "rag_index_source_chunks",
        sa.Column("index_source_chunk_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("source_ordinal", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("chunk_text_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["embedding_index_id"],
            ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_sources__index", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["plm.rag_document_chunks.chunk_id"],
            name="fk_rag_index_sources__chunk", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_sources__project", ondelete="NO ACTION"),
        sa.UniqueConstraint(
            "embedding_index_id", "source_ordinal",
            name="uq_rag_index_sources__ordinal"),
        sa.UniqueConstraint(
            "embedding_index_id", "chunk_id",
            name="uq_rag_index_sources__chunk"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_sources__scope_project"),
        sa.CheckConstraint(
            "source_ordinal BETWEEN 1 AND 1000000000 "
            "AND octet_length(chunk_text_fingerprint)=32 "
            "AND created_xid>0",
            name="ck_rag_index_sources__shape"),
        schema="plm",
    )
    op.create_index(
        "ix_rag_index_sources__chunk", "rag_index_source_chunks",
        ["chunk_id", "embedding_index_id"], schema="plm",
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG EmbeddingIndex downgrade is disabled")
    op.execute("LOCK TABLE plm.rag_index_source_chunks, "
               "plm.rag_embedding_indexes IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_indexes)
               OR EXISTS (SELECT 1 FROM plm.rag_index_source_chunks) THEN
                RAISE EXCEPTION 'RAG EmbeddingIndex history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_index_source_chunk_no_truncate "
               "ON plm.rag_index_source_chunks")
    op.execute("DROP TRIGGER trg_rag_embedding_index_no_truncate "
               "ON plm.rag_embedding_indexes")
    op.execute("DROP TRIGGER trg_rag_index_source_snapshot_complete "
               "ON plm.rag_embedding_indexes")
    op.execute("DROP TRIGGER trg_rag_index_source_chunk_guard "
               "ON plm.rag_index_source_chunks")
    op.execute("DROP TRIGGER trg_rag_embedding_index_guard "
               "ON plm.rag_embedding_indexes")
    op.execute("DROP FUNCTION plm.guard_rag_index_foundation_truncate()")
    op.execute("DROP FUNCTION plm.validate_rag_index_source_snapshot()")
    op.execute("DROP FUNCTION plm.guard_rag_index_source_chunk()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_index()")
    op.drop_index("ix_rag_index_sources__chunk",
                  table_name="rag_index_source_chunks", schema="plm")
    op.drop_table("rag_index_source_chunks", schema="plm")
    op.drop_index("ix_rag_indexes__project_purpose_version",
                  table_name="rag_embedding_indexes", schema="plm")
    op.drop_index("uq_rag_indexes__active_purpose",
                  table_name="rag_embedding_indexes", schema="plm")
    op.drop_table("rag_embedding_indexes", schema="plm")
