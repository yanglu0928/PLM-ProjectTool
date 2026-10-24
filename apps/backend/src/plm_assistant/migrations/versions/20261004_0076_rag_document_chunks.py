"""Add source-bound RAG DocumentChunk and full-text projection.

Revision ID: 20261004_0076
Revises: 20261003_0075
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261004_0076"
down_revision = "20261003_0075"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_document_chunk()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    version_scope text;
    version_project uuid;
    version_state text;
    document_category text;
    record plm.doc_parse_records%ROWTYPE;
    result plm.doc_parse_result_refs%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'RAG DocumentChunk history is retained';
    END IF;
    IF TG_OP='UPDATE' THEN
        IF ROW(NEW.chunk_id,NEW.scope,NEW.project_id,NEW.document_version_ref,
               NEW.parse_record_ref,NEW.parse_result_ref,NEW.chunk_profile,
               NEW.chunk_profile_version,NEW.chunk_ordinal,NEW.source_locator,
               NEW.source_type,NEW.search_body,NEW.text_fingerprint,
               NEW.metadata_snapshot,NEW.created_by,NEW.created_at)
           IS DISTINCT FROM
           ROW(OLD.chunk_id,OLD.scope,OLD.project_id,OLD.document_version_ref,
               OLD.parse_record_ref,OLD.parse_result_ref,OLD.chunk_profile,
               OLD.chunk_profile_version,OLD.chunk_ordinal,OLD.source_locator,
               OLD.source_type,OLD.search_body,OLD.text_fingerprint,
               OLD.metadata_snapshot,OLD.created_by,OLD.created_at)
           OR NEW.lock_version<>OLD.lock_version+1
           OR (OLD.chunk_state='ACTIVE' AND NEW.chunk_state NOT IN ('RESTRICTED','REVOKED'))
           OR (OLD.chunk_state='RESTRICTED' AND NEW.chunk_state NOT IN ('ACTIVE','REVOKED'))
           OR OLD.chunk_state='REVOKED' THEN
            RAISE EXCEPTION 'RAG DocumentChunk immutable source or state transition is invalid';
        END IF;
    ELSIF NEW.lock_version<>0 OR NEW.chunk_state<>'ACTIVE' THEN
        RAISE EXCEPTION 'RAG DocumentChunk must start ACTIVE at version zero';
    END IF;

    SELECT version.scope,version.project_id,version.availability_state,
           document.document_category
      INTO version_scope,version_project,version_state,document_category
      FROM plm.doc_document_versions version
      JOIN plm.doc_documents document ON document.document_id=version.document_id
     WHERE version.document_version_id=NEW.document_version_ref
     FOR KEY SHARE OF version,document;
    SELECT * INTO record FROM plm.doc_parse_records
     WHERE parse_record_id=NEW.parse_record_ref FOR KEY SHARE;
    SELECT * INTO result FROM plm.doc_parse_result_refs
     WHERE parse_result_ref_id=NEW.parse_result_ref FOR KEY SHARE;
    IF version_scope IS NULL OR record.parse_record_id IS NULL
       OR result.parse_result_ref_id IS NULL
       OR ROW(NEW.scope,NEW.project_id) IS DISTINCT FROM
          ROW(version_scope,version_project)
       OR NEW.source_type IS DISTINCT FROM document_category
       OR ROW(record.document_version_id,record.scope,record.project_id,
              record.parse_state,record.result_ref,record.result_sha256)
          IS DISTINCT FROM
          ROW(NEW.document_version_ref,NEW.scope,NEW.project_id,
              'SUCCEEDED',NEW.parse_result_ref,result.sha256)
       OR result.parse_record_id IS DISTINCT FROM NEW.parse_record_ref
       OR NEW.text_fingerprint IS DISTINCT FROM
          sha256(convert_to(NEW.search_body,'UTF8')) THEN
        RAISE EXCEPTION 'RAG DocumentChunk source binding is invalid';
    END IF;
    IF TG_OP='INSERT' AND version_state<>'AVAILABLE'
       OR NEW.chunk_state='ACTIVE' AND version_state<>'AVAILABLE'
       OR NEW.chunk_state='RESTRICTED' AND version_state='REVOKED' THEN
        RAISE EXCEPTION 'RAG DocumentChunk source availability is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_document_chunk_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.rag_document_chunks
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_document_chunk();

CREATE FUNCTION plm.guard_rag_document_chunk_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RAG DocumentChunk history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_document_chunk_no_truncate
BEFORE TRUNCATE ON plm.rag_document_chunks
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_document_chunk_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "rag_document_chunks",
        sa.Column("chunk_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("document_version_ref", ident, nullable=False),
        sa.Column("parse_record_ref", ident, nullable=False),
        sa.Column("parse_result_ref", ident, nullable=False),
        sa.Column("chunk_profile", sa.Text(), nullable=False),
        sa.Column("chunk_profile_version", sa.Integer(), nullable=False),
        sa.Column("chunk_ordinal", sa.Integer(), nullable=False),
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("search_body", sa.Text(), nullable=False),
        sa.Column(
            "search_vector", postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple'::regconfig, search_body)",
                        persisted=True),
        ),
        sa.Column("text_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("metadata_snapshot", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("chunk_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_chunks__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_version_ref"],
            ["plm.doc_document_versions.document_version_id"],
            name="fk_rag_chunks__document_version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["parse_record_ref"], ["plm.doc_parse_records.parse_record_id"],
            name="fk_rag_chunks__parse_record", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["parse_result_ref"],
            ["plm.doc_parse_result_refs.parse_result_ref_id"],
            name="fk_rag_chunks__parse_result", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_rag_chunks__creator", ondelete="NO ACTION"),
        sa.UniqueConstraint(
            "document_version_ref", "parse_record_ref", "chunk_profile",
            "chunk_profile_version", "chunk_ordinal",
            name="uq_rag_chunks__source_generation_ordinal"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_chunks__scope_project"),
        sa.CheckConstraint(
            "chunk_profile ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND chunk_profile_version BETWEEN 1 AND 2147483647 "
            "AND chunk_ordinal BETWEEN 0 AND 2147483647",
            name="ck_rag_chunks__generation"),
        sa.CheckConstraint(
            "jsonb_typeof(source_locator)='object' "
            "AND source_locator ? 'locator_type'",
            name="ck_rag_chunks__locator"),
        sa.CheckConstraint(
            "source_type IN ('CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY',"
            "'REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER')",
            name="ck_rag_chunks__source_type"),
        sa.CheckConstraint(
            "char_length(search_body) BETWEEN 1 AND 65535 "
            "AND octet_length(text_fingerprint)=32",
            name="ck_rag_chunks__text"),
        sa.CheckConstraint(
            "jsonb_typeof(metadata_snapshot)='object'",
            name="ck_rag_chunks__metadata"),
        sa.CheckConstraint(
            "chunk_state IN ('ACTIVE','RESTRICTED','REVOKED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND isfinite(created_at)",
            name="ck_rag_chunks__state"),
        schema="plm",
    )
    op.create_index(
        "ix_rag_chunks__search_gin", "rag_document_chunks",
        ["search_vector"], schema="plm", postgresql_using="gin",
    )
    op.create_index(
        "ix_rag_chunks__project_source_state", "rag_document_chunks",
        ["project_id", "document_version_ref", "chunk_state", "chunk_id"],
        schema="plm",
    )
    op.create_index(
        "ix_rag_chunks__global_source_state", "rag_document_chunks",
        ["document_version_ref", "chunk_state", "chunk_id"], schema="plm",
        postgresql_where=sa.text("scope='GLOBAL'"),
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG DocumentChunk downgrade is disabled")
    op.execute("LOCK TABLE plm.rag_document_chunks IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_document_chunks) THEN
                RAISE EXCEPTION 'RAG DocumentChunk history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_document_chunk_no_truncate "
               "ON plm.rag_document_chunks")
    op.execute("DROP TRIGGER trg_rag_document_chunk_guard "
               "ON plm.rag_document_chunks")
    op.execute("DROP FUNCTION plm.guard_rag_document_chunk_truncate()")
    op.execute("DROP FUNCTION plm.guard_rag_document_chunk()")
    op.drop_index("ix_rag_chunks__global_source_state",
                  table_name="rag_document_chunks", schema="plm")
    op.drop_index("ix_rag_chunks__project_source_state",
                  table_name="rag_document_chunks", schema="plm")
    op.drop_index("ix_rag_chunks__search_gin",
                  table_name="rag_document_chunks", schema="plm")
    op.drop_table("rag_document_chunks", schema="plm")
