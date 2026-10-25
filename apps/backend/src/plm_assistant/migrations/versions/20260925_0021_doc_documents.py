"""DOC-01 Document logical identity before immutable versions.

Revision ID: 20260925_0021
Revises: 20260925_0020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0021"
down_revision = "20260925_0020"
branch_labels = None
depends_on = None


_CATEGORIES = "'CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY','REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER'"


def upgrade() -> None:
    op.create_table(
        "doc_documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("document_category", sa.Text(), nullable=False),
        sa.Column("document_subtype", sa.Text()),
        sa.Column("document_purpose", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_display_name", sa.Text(), nullable=False),
        sa.Column("document_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("latest_version_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("effective_version_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("document_id", "scope", "project_id",
                            name="uq_doc_documents__id_scope_project",
                            postgresql_nulls_not_distinct=True),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_doc_documents__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_doc_documents__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_doc_documents__updater", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_doc_documents__scope_project"),
        sa.CheckConstraint(f"document_category IN ({_CATEGORIES})",
                           name="ck_doc_documents__category"),
        sa.CheckConstraint("document_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                           name="ck_doc_documents__state"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                           name="ck_doc_documents__title"),
        sa.CheckConstraint("char_length(original_display_name) BETWEEN 1 AND 255 AND original_display_name=btrim(original_display_name)",
                           name="ck_doc_documents__display_name"),
        sa.CheckConstraint("document_subtype IS NULL OR (char_length(document_subtype) BETWEEN 1 AND 128 AND document_subtype=btrim(document_subtype))",
                           name="ck_doc_documents__subtype"),
        sa.CheckConstraint("document_purpose IS NULL OR (char_length(document_purpose) BETWEEN 1 AND 255 AND document_purpose=btrim(document_purpose))",
                           name="ck_doc_documents__purpose"),
        sa.CheckConstraint("document_category <> 'OTHER' OR (document_subtype IS NOT NULL AND document_purpose IS NOT NULL)",
                           name="ck_doc_documents__other_details"),
        sa.CheckConstraint("document_category <> 'GENERATED_ARTIFACT' OR scope='PROJECT'",
                           name="ck_doc_documents__generated_scope"),
        sa.CheckConstraint("latest_version_ref IS NULL AND effective_version_ref IS NULL",
                           name="ck_doc_documents__pre_version_pointers"),
        sa.CheckConstraint("lock_version >= 0", name="ck_doc_documents__version"),
        schema="plm",
    )
    op.create_index("ix_doc_documents__scope_project_state", "doc_documents",
                    ["scope", "project_id", "document_state"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.reject_document_identity_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.document_id IS DISTINCT FROM OLD.document_id
               OR NEW.scope IS DISTINCT FROM OLD.scope
               OR NEW.project_id IS DISTINCT FROM OLD.project_id THEN
                RAISE EXCEPTION 'document identity is immutable';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_documents_identity_immutable
        BEFORE UPDATE ON plm.doc_documents
        FOR EACH ROW EXECUTE FUNCTION plm.reject_document_identity_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for Document metadata")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_documents)")):
        raise RuntimeError("Document metadata exists; downgrade refused")
    op.execute("DROP TRIGGER trg_doc_documents_identity_immutable ON plm.doc_documents")
    op.execute("DROP FUNCTION plm.reject_document_identity_mutation()")
    op.drop_index("ix_doc_documents__scope_project_state", table_name="doc_documents",
                  schema="plm")
    op.drop_table("doc_documents", schema="plm")
