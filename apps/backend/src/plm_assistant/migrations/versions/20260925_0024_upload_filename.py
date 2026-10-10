"""Require upload display name for new intents targeting existing Documents.

Revision ID: 20260925_0024
Revises: 20260925_0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op


revision = "20260925_0024"
down_revision = "20260925_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_doc_upload_intents__existing_document", "doc_upload_intents",
                       schema="plm", type_="check")
    op.create_check_constraint(
        "ck_doc_upload_intents__existing_document", "doc_upload_intents",
        "target_document_id IS NULL OR (document_category IS NULL AND document_subtype IS NULL AND document_purpose IS NULL AND title IS NULL)",
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.require_upload_intent_display_name()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.original_display_name IS NULL THEN
                RAISE EXCEPTION 'upload display name required';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_upload_intents_require_name
        BEFORE INSERT ON plm.doc_upload_intents
        FOR EACH ROW EXECUTE FUNCTION plm.require_upload_intent_display_name()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for UploadIntent name correction")
    bind = op.get_bind()
    if bind.scalar(sa.text("""
        SELECT EXISTS (SELECT 1 FROM plm.doc_upload_intents
                       WHERE target_document_id IS NOT NULL
                         AND original_display_name IS NOT NULL)
    """)):
        raise RuntimeError("named existing-document upload intents exist; downgrade refused")
    op.execute("DROP TRIGGER trg_doc_upload_intents_require_name ON plm.doc_upload_intents")
    op.execute("DROP FUNCTION plm.require_upload_intent_display_name()")
    op.drop_constraint("ck_doc_upload_intents__existing_document", "doc_upload_intents",
                       schema="plm", type_="check")
    op.create_check_constraint(
        "ck_doc_upload_intents__existing_document", "doc_upload_intents",
        "target_document_id IS NULL OR (document_category IS NULL AND document_subtype IS NULL AND document_purpose IS NULL AND title IS NULL AND original_display_name IS NULL)",
        schema="plm",
    )
