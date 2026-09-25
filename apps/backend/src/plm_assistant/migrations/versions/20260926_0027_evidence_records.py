"""EVD-01 fixed DocumentVersion evidence records.

Revision ID: 20260926_0027
Revises: 20260926_0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260926_0027"
down_revision = "20260926_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evd_evidence_records",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locator_type", sa.Text(), nullable=False),
        sa.Column("locator_schema_version", sa.Integer(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("locator_payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("display_label", sa.Text(), nullable=False),
        sa.Column("display_excerpt", sa.Text()),
        sa.Column("eligibility_state", sa.Text(), nullable=False,
                  server_default=sa.text("'CANDIDATE'")),
        sa.Column("eligibility_reason", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_evd_evidence__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["document_version_id", "document_id"],
                                ["plm.doc_document_versions.document_version_id",
                                 "plm.doc_document_versions.document_id"],
                                name="fk_evd_evidence__version_document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_evd_evidence__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_evd_evidence__updater", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_evd_evidence__scope_project"),
        sa.CheckConstraint("locator_type IN ('DOCUMENT','PAGE','TEXT_RANGE','SECTION','PARAGRAPH','TABLE_CELL','SHEET_RANGE','SLIDE_SHAPE','STRUCTURED_NODE')",
                           name="ck_evd_evidence__locator_type"),
        sa.CheckConstraint("locator_schema_version=1", name="ck_evd_evidence__locator_version"),
        sa.CheckConstraint("jsonb_typeof(locator_payload)='object' AND locator_payload ? 'locator_type' AND locator_payload->>'locator_type'=locator_type",
                           name="ck_evd_evidence__locator_payload"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32", name="ck_evd_evidence__fingerprint"),
        sa.CheckConstraint("char_length(display_label) BETWEEN 1 AND 255 AND display_label=btrim(display_label)",
                           name="ck_evd_evidence__label"),
        sa.CheckConstraint("display_excerpt IS NULL OR char_length(display_excerpt) BETWEEN 1 AND 500",
                           name="ck_evd_evidence__excerpt"),
        sa.CheckConstraint("eligibility_state IN ('CANDIDATE','ELIGIBLE','INELIGIBLE','REVOKED')",
                           name="ck_evd_evidence__eligibility"),
        sa.CheckConstraint("eligibility_reason IS NULL OR (char_length(eligibility_reason) BETWEEN 1 AND 1024 AND eligibility_reason=btrim(eligibility_reason))",
                           name="ck_evd_evidence__reason"),
        sa.CheckConstraint("(eligibility_state='CANDIDATE' AND eligibility_reason IS NULL) OR (eligibility_state<>'CANDIDATE' AND eligibility_reason IS NOT NULL)",
                           name="ck_evd_evidence__reason_state"),
        sa.CheckConstraint("lock_version >= 0", name="ck_evd_evidence__version"),
        schema="plm",
    )
    op.create_index("ix_evd_evidence__scope_project_created", "evd_evidence_records",
                    ["scope", "project_id", "created_at", "evidence_id"], schema="plm")
    op.create_index("ix_evd_evidence__document_version", "evd_evidence_records",
                    ["document_version_id", "evidence_id"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_evidence_record()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_scope text;
            source_project uuid;
            source_state text;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'evidence history is retained';
            END IF;
            IF TG_OP='INSERT' THEN
                SELECT scope, project_id, availability_state
                  INTO source_scope, source_project, source_state
                  FROM plm.doc_document_versions
                 WHERE document_version_id=NEW.document_version_id
                   AND document_id=NEW.document_id FOR SHARE;
                IF NOT FOUND OR source_scope IS DISTINCT FROM NEW.scope
                   OR source_project IS DISTINCT FROM NEW.project_id
                   OR source_state <> 'AVAILABLE'
                   OR NEW.eligibility_state <> 'CANDIDATE'
                   OR NEW.eligibility_reason IS NOT NULL
                   OR NEW.lock_version <> 0 THEN
                    RAISE EXCEPTION 'evidence source or initial state invalid';
                END IF;
                RETURN NEW;
            END IF;
            IF ROW(NEW.evidence_id,NEW.scope,NEW.project_id,NEW.document_id,
                   NEW.document_version_id,NEW.locator_type,
                   NEW.locator_schema_version,NEW.locator_payload,
                   NEW.content_fingerprint,NEW.created_by,NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.evidence_id,OLD.scope,OLD.project_id,OLD.document_id,
                   OLD.document_version_id,OLD.locator_type,
                   OLD.locator_schema_version,OLD.locator_payload,
                   OLD.content_fingerprint,OLD.created_by,OLD.created_at) THEN
                RAISE EXCEPTION 'evidence source is immutable';
            END IF;
            IF OLD.eligibility_state='REVOKED' AND NEW.eligibility_state<>'REVOKED' THEN
                RAISE EXCEPTION 'revoked evidence cannot be restored';
            END IF;
            IF NEW.lock_version <> OLD.lock_version+1 OR NEW.updated_by IS NULL
               OR NEW.updated_at < OLD.updated_at THEN
                RAISE EXCEPTION 'evidence mutation version invalid';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_evd_evidence_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.evd_evidence_records
        FOR EACH ROW EXECUTE FUNCTION plm.guard_evidence_record()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for Evidence")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.evd_evidence_records)")):
        raise RuntimeError("Evidence history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_evd_evidence_guard ON plm.evd_evidence_records")
    op.execute("DROP FUNCTION plm.guard_evidence_record()")
    op.drop_index("ix_evd_evidence__document_version", table_name="evd_evidence_records", schema="plm")
    op.drop_index("ix_evd_evidence__scope_project_created", table_name="evd_evidence_records", schema="plm")
    op.drop_table("evd_evidence_records", schema="plm")
