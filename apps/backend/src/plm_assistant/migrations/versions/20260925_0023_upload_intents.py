"""Private durable UploadIntent for the frozen three-step document protocol.

Revision ID: 20260925_0023
Revises: 20260925_0022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0023"
down_revision = "20260925_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doc_upload_intents",
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_document_id", postgresql.UUID(as_uuid=True)),
        sa.Column("document_category", sa.Text()),
        sa.Column("document_subtype", sa.Text()),
        sa.Column("document_purpose", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("original_display_name", sa.Text()),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger()),
        sa.Column("mime_hint", sa.Text()),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'CREATED'")),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.Column("file_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("committed_document_id", postgresql.UUID(as_uuid=True)),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_doc_upload_intents__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_doc_upload_intents__actor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["target_document_id"], ["plm.doc_documents.document_id"],
                                name="fk_doc_upload_intents__target_document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["committed_document_id"], ["plm.doc_documents.document_id"],
                                name="fk_doc_upload_intents__committed_document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["file_object_id"], ["plm.doc_file_objects.file_object_id"],
                                name="fk_doc_upload_intents__file", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["document_version_id"], ["plm.doc_document_versions.document_version_id"],
                                name="fk_doc_upload_intents__version", ondelete="NO ACTION"),
        sa.UniqueConstraint("token_digest", name="uq_doc_upload_intents__token_digest"),
        sa.UniqueConstraint("file_object_id", name="uq_doc_upload_intents__file"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_doc_upload_intents__scope_project"),
        sa.CheckConstraint("state IN ('CREATED','CONTENT_READY','COMMITTED','ABORTED','EXPIRED')",
                           name="ck_doc_upload_intents__state"),
        sa.CheckConstraint("octet_length(token_digest)=32", name="ck_doc_upload_intents__token_digest"),
        sa.CheckConstraint("expires_at > created_at", name="ck_doc_upload_intents__expiry"),
        sa.CheckConstraint("lock_version >= 0", name="ck_doc_upload_intents__version"),
        sa.CheckConstraint("expected_size_bytes IS NULL OR expected_size_bytes >= 0",
                           name="ck_doc_upload_intents__size"),
        sa.CheckConstraint("mime_hint IS NULL OR char_length(mime_hint) BETWEEN 1 AND 255",
                           name="ck_doc_upload_intents__mime"),
        sa.CheckConstraint("char_length(purpose_code) BETWEEN 1 AND 64 AND purpose_code ~ '^[A-Z][A-Z0-9_]*$'",
                           name="ck_doc_upload_intents__purpose"),
        sa.CheckConstraint("target_document_id IS NOT NULL OR (document_category IS NOT NULL AND title IS NOT NULL AND original_display_name IS NOT NULL)",
                           name="ck_doc_upload_intents__new_document"),
        sa.CheckConstraint("target_document_id IS NULL OR (document_category IS NULL AND document_subtype IS NULL AND document_purpose IS NULL AND title IS NULL AND original_display_name IS NULL)",
                           name="ck_doc_upload_intents__existing_document"),
        sa.CheckConstraint("document_category IS NULL OR document_category IN ('CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY','REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER')",
                           name="ck_doc_upload_intents__category"),
        sa.CheckConstraint("document_category IS DISTINCT FROM 'OTHER' OR (document_subtype IS NOT NULL AND document_purpose IS NOT NULL)",
                           name="ck_doc_upload_intents__other_details"),
        sa.CheckConstraint("document_category IS DISTINCT FROM 'GENERATED_ARTIFACT' OR scope='PROJECT'",
                           name="ck_doc_upload_intents__generated_scope"),
        sa.CheckConstraint("title IS NULL OR (char_length(title) BETWEEN 1 AND 255 AND title=btrim(title))",
                           name="ck_doc_upload_intents__title"),
        sa.CheckConstraint("original_display_name IS NULL OR (char_length(original_display_name) BETWEEN 1 AND 255 AND original_display_name=btrim(original_display_name))",
                           name="ck_doc_upload_intents__name"),
        sa.CheckConstraint("document_subtype IS NULL OR (char_length(document_subtype) BETWEEN 1 AND 128 AND document_subtype=btrim(document_subtype))",
                           name="ck_doc_upload_intents__subtype"),
        sa.CheckConstraint("document_purpose IS NULL OR (char_length(document_purpose) BETWEEN 1 AND 255 AND document_purpose=btrim(document_purpose))",
                           name="ck_doc_upload_intents__document_purpose"),
        sa.CheckConstraint("(state='CREATED' AND file_object_id IS NULL AND committed_document_id IS NULL AND document_version_id IS NULL) OR (state='CONTENT_READY' AND file_object_id IS NOT NULL AND committed_document_id IS NULL AND document_version_id IS NULL) OR (state='COMMITTED' AND file_object_id IS NOT NULL AND committed_document_id IS NOT NULL AND document_version_id IS NOT NULL) OR (state IN ('ABORTED','EXPIRED') AND committed_document_id IS NULL AND document_version_id IS NULL)",
                           name="ck_doc_upload_intents__state_shape"),
        schema="plm",
    )
    op.create_index("ix_doc_upload_intents__actor_state_expiry", "doc_upload_intents",
                    ["actor_id", "state", "expires_at"], schema="plm")
    op.create_index("ix_doc_upload_intents__project_state_expiry", "doc_upload_intents",
                    ["project_id", "state", "expires_at"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_document_upload_intent()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            d plm.doc_documents%ROWTYPE;
            f plm.doc_file_objects%ROWTYPE;
            v plm.doc_document_versions%ROWTYPE;
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.state <> 'CREATED' OR NEW.lock_version <> 0 THEN
                    RAISE EXCEPTION 'upload intent initial state invalid';
                END IF;
            ELSE
                IF ROW(NEW.upload_id,NEW.scope,NEW.project_id,NEW.actor_id,
                       NEW.target_document_id,NEW.document_category,NEW.document_subtype,
                       NEW.document_purpose,NEW.title,NEW.original_display_name,
                       NEW.purpose_code,NEW.expected_size_bytes,NEW.mime_hint,
                       NEW.token_digest,NEW.expires_at,NEW.created_at)
                   IS DISTINCT FROM
                   ROW(OLD.upload_id,OLD.scope,OLD.project_id,OLD.actor_id,
                       OLD.target_document_id,OLD.document_category,OLD.document_subtype,
                       OLD.document_purpose,OLD.title,OLD.original_display_name,
                       OLD.purpose_code,OLD.expected_size_bytes,OLD.mime_hint,
                       OLD.token_digest,OLD.expires_at,OLD.created_at) THEN
                    RAISE EXCEPTION 'upload intent identity is immutable';
                END IF;
                IF OLD.state IN ('COMMITTED','ABORTED','EXPIRED')
                   OR NOT ((OLD.state='CREATED' AND NEW.state IN ('CONTENT_READY','ABORTED','EXPIRED'))
                           OR (OLD.state='CONTENT_READY' AND NEW.state IN ('COMMITTED','ABORTED','EXPIRED')))
                   OR NEW.lock_version <> OLD.lock_version + 1
                   OR NEW.updated_at < OLD.updated_at
                   OR (OLD.file_object_id IS NOT NULL AND NEW.file_object_id IS DISTINCT FROM OLD.file_object_id) THEN
                    RAISE EXCEPTION 'upload intent transition invalid';
                END IF;
            END IF;
            IF NEW.target_document_id IS NOT NULL THEN
                SELECT * INTO d FROM plm.doc_documents WHERE document_id=NEW.target_document_id;
                IF NOT FOUND OR d.scope IS DISTINCT FROM NEW.scope
                   OR d.project_id IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'upload target document scope invalid';
                END IF;
            END IF;
            IF NEW.file_object_id IS NOT NULL THEN
                SELECT * INTO f FROM plm.doc_file_objects WHERE file_object_id=NEW.file_object_id;
                IF NOT FOUND OR f.scope IS DISTINCT FROM NEW.scope
                   OR f.project_id IS DISTINCT FROM NEW.project_id
                   OR f.storage_class <> 'PERSISTENT'
                   OR (NEW.state='CONTENT_READY' AND f.file_state <> 'STAGED')
                   OR (NEW.state='COMMITTED' AND f.file_state <> 'AVAILABLE') THEN
                    RAISE EXCEPTION 'upload content scope or state invalid';
                END IF;
            END IF;
            IF NEW.committed_document_id IS NOT NULL THEN
                SELECT * INTO d FROM plm.doc_documents WHERE document_id=NEW.committed_document_id;
                IF NOT FOUND OR d.scope IS DISTINCT FROM NEW.scope
                   OR d.project_id IS DISTINCT FROM NEW.project_id
                   OR (NEW.target_document_id IS NOT NULL
                       AND NEW.committed_document_id IS DISTINCT FROM NEW.target_document_id) THEN
                    RAISE EXCEPTION 'upload committed document scope invalid';
                END IF;
            END IF;
            IF NEW.document_version_id IS NOT NULL THEN
                SELECT * INTO v FROM plm.doc_document_versions
                 WHERE document_version_id=NEW.document_version_id;
                IF NOT FOUND OR v.document_id IS DISTINCT FROM NEW.committed_document_id
                   OR v.file_object_id IS DISTINCT FROM NEW.file_object_id
                   OR v.scope IS DISTINCT FROM NEW.scope
                   OR v.project_id IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'upload committed version invalid';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_upload_intents_guard
        BEFORE INSERT OR UPDATE ON plm.doc_upload_intents
        FOR EACH ROW EXECUTE FUNCTION plm.guard_document_upload_intent()
    """)
    op.execute("""
        CREATE FUNCTION plm.reject_document_upload_intent_delete()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'upload intent history is retained';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_upload_intents_delete_guard
        BEFORE DELETE ON plm.doc_upload_intents
        FOR EACH ROW EXECUTE FUNCTION plm.reject_document_upload_intent_delete()
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_upload_intents_truncate_guard
        BEFORE TRUNCATE ON plm.doc_upload_intents
        FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_document_upload_intent_delete()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for UploadIntent")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_upload_intents)")):
        raise RuntimeError("UploadIntent history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_doc_upload_intents_truncate_guard ON plm.doc_upload_intents")
    op.execute("DROP TRIGGER trg_doc_upload_intents_delete_guard ON plm.doc_upload_intents")
    op.execute("DROP FUNCTION plm.reject_document_upload_intent_delete()")
    op.execute("DROP TRIGGER trg_doc_upload_intents_guard ON plm.doc_upload_intents")
    op.execute("DROP FUNCTION plm.guard_document_upload_intent()")
    op.drop_index("ix_doc_upload_intents__project_state_expiry", table_name="doc_upload_intents", schema="plm")
    op.drop_index("ix_doc_upload_intents__actor_state_expiry", table_name="doc_upload_intents", schema="plm")
    op.drop_table("doc_upload_intents", schema="plm")
