"""DOC-04 retained parse attempts and opaque result references.

Revision ID: 20260926_0028
Revises: 20260926_0027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260926_0028"
down_revision = "20260926_0027"
branch_labels = None
depends_on = None

_ID = postgresql.UUID(as_uuid=True)
_TIME = postgresql.TIMESTAMP(timezone=True, precision=6)


def upgrade() -> None:
    op.create_table(
        "doc_parse_records",
        sa.Column("parse_record_id", _ID, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("document_version_id", _ID, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", _ID),
        sa.Column("parser_profile", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("job_ref", _ID, nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("parse_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("result_ref", _ID),
        sa.Column("result_sha256", sa.LargeBinary()),
        sa.Column("started_at", _TIME),
        sa.Column("completed_at", _TIME),
        sa.Column("error_code", sa.Text()),
        sa.Column("retryable", sa.Boolean()),
        sa.Column("created_at", _TIME, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("document_version_id", "parser_profile", "parser_version",
                            "attempt_no", name="uq_doc_parse_records__attempt"),
        sa.UniqueConstraint("job_ref", "attempt_no", name="uq_doc_parse_records__job_attempt"),
        sa.UniqueConstraint("result_ref", name="uq_doc_parse_records__result"),
        sa.ForeignKeyConstraint(["document_version_id"],
                                ["plm.doc_document_versions.document_version_id"],
                                name="fk_doc_parse_records__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["job_ref"], ["plm.job_jobs.job_id"],
                                name="fk_doc_parse_records__job", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_doc_parse_records__project", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_doc_parse_records__scope"),
        sa.CheckConstraint("char_length(parser_profile) BETWEEN 1 AND 128 AND parser_profile=btrim(parser_profile)",
                           name="ck_doc_parse_records__profile"),
        sa.CheckConstraint("char_length(parser_version) BETWEEN 1 AND 64 AND parser_version=btrim(parser_version)",
                           name="ck_doc_parse_records__parser_version"),
        sa.CheckConstraint("attempt_no > 0 AND lock_version >= 0",
                           name="ck_doc_parse_records__counters"),
        sa.CheckConstraint("parse_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
                           name="ck_doc_parse_records__state"),
        sa.CheckConstraint("completed_at IS NULL OR (started_at IS NULL OR completed_at >= started_at)",
                           name="ck_doc_parse_records__time"),
        sa.CheckConstraint("result_sha256 IS NULL OR octet_length(result_sha256)=32",
                           name="ck_doc_parse_records__result_sha"),
        sa.CheckConstraint("error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                           name="ck_doc_parse_records__error"),
        sa.CheckConstraint("(parse_state='PENDING' AND started_at IS NULL AND completed_at IS NULL AND result_ref IS NULL AND result_sha256 IS NULL AND error_code IS NULL AND retryable IS NULL) OR (parse_state='RUNNING' AND started_at IS NOT NULL AND completed_at IS NULL AND result_ref IS NULL AND result_sha256 IS NULL AND error_code IS NULL AND retryable IS NULL) OR (parse_state='SUCCEEDED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND result_ref IS NOT NULL AND result_sha256 IS NOT NULL AND error_code IS NULL AND retryable IS FALSE) OR (parse_state='FAILED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND result_ref IS NULL AND result_sha256 IS NULL AND error_code IS NOT NULL AND retryable IS NOT NULL) OR (parse_state='CANCELLED' AND completed_at IS NOT NULL AND result_ref IS NULL AND result_sha256 IS NULL AND retryable IS FALSE)",
                           name="ck_doc_parse_records__shape"),
        schema="plm",
    )
    op.create_index("ix_doc_parse_records__version_created", "doc_parse_records",
                    ["document_version_id", "created_at", "parse_record_id"], schema="plm")
    op.create_table(
        "doc_parse_result_refs",
        sa.Column("parse_result_ref_id", _ID, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("parse_record_id", _ID, nullable=False),
        sa.Column("storage_locator", sa.Text(), nullable=False),
        sa.Column("result_schema_version", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", _TIME, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("parse_record_id", name="uq_doc_parse_result_refs__record"),
        sa.ForeignKeyConstraint(["parse_record_id"], ["plm.doc_parse_records.parse_record_id"],
                                name="fk_doc_parse_result_refs__record", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(storage_locator) BETWEEN 1 AND 1024 AND left(storage_locator,1)<>'/' AND position('..' in storage_locator)=0 AND position(':' in storage_locator)=0 AND position(chr(92) in storage_locator)=0",
                           name="ck_doc_parse_result_refs__locator"),
        sa.CheckConstraint("result_schema_version > 0 AND size_bytes >= 0",
                           name="ck_doc_parse_result_refs__numbers"),
        sa.CheckConstraint("octet_length(sha256)=32",
                           name="ck_doc_parse_result_refs__sha"),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_parse_record()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v plm.doc_document_versions%ROWTYPE;
            j plm.job_jobs%ROWTYPE;
            result_row plm.doc_parse_result_refs%ROWTYPE;
            next_attempt integer;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'parse history is retained';
            END IF;
            IF TG_OP='INSERT' THEN
                SELECT * INTO v FROM plm.doc_document_versions
                 WHERE document_version_id=NEW.document_version_id FOR UPDATE;
                IF NOT FOUND OR v.scope IS DISTINCT FROM NEW.scope
                   OR v.project_id IS DISTINCT FROM NEW.project_id
                   OR v.availability_state <> 'AVAILABLE' THEN
                    RAISE EXCEPTION 'parse source invalid';
                END IF;
                SELECT * INTO j FROM plm.job_jobs WHERE job_id=NEW.job_ref FOR SHARE;
                IF NOT FOUND OR j.owner_module <> 'document'
                   OR j.job_type <> 'DOCUMENT_PARSE'
                   OR j.scope IS DISTINCT FROM NEW.scope
                   OR j.project_id IS DISTINCT FROM NEW.project_id
                   OR j.payload_refs->>'document_version_id' IS DISTINCT FROM NEW.document_version_id::text
                   OR j.payload_refs->>'document_id' IS DISTINCT FROM v.document_id::text
                   OR NEW.parse_state <> 'PENDING' OR NEW.lock_version <> 0 THEN
                    RAISE EXCEPTION 'parse job or initial state invalid';
                END IF;
                SELECT coalesce(max(attempt_no),0)+1 INTO next_attempt
                  FROM plm.doc_parse_records
                 WHERE document_version_id=NEW.document_version_id
                   AND parser_profile=NEW.parser_profile
                   AND parser_version=NEW.parser_version;
                IF NEW.attempt_no <> next_attempt THEN
                    RAISE EXCEPTION 'parse attempt sequence invalid';
                END IF;
                RETURN NEW;
            END IF;
            IF ROW(NEW.parse_record_id,NEW.document_version_id,NEW.scope,
                   NEW.project_id,NEW.parser_profile,NEW.parser_version,
                   NEW.job_ref,NEW.attempt_no,NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.parse_record_id,OLD.document_version_id,OLD.scope,
                   OLD.project_id,OLD.parser_profile,OLD.parser_version,
                   OLD.job_ref,OLD.attempt_no,OLD.created_at) THEN
                RAISE EXCEPTION 'parse identity is immutable';
            END IF;
            IF OLD.parse_state IN ('SUCCEEDED','FAILED','CANCELLED')
               OR NOT ((OLD.parse_state='PENDING' AND NEW.parse_state IN ('RUNNING','CANCELLED'))
                    OR (OLD.parse_state='RUNNING' AND NEW.parse_state IN ('SUCCEEDED','FAILED','CANCELLED')))
               OR NEW.lock_version <> OLD.lock_version+1 THEN
                RAISE EXCEPTION 'parse transition invalid';
            END IF;
            IF NEW.parse_state='SUCCEEDED' THEN
                SELECT * INTO result_row FROM plm.doc_parse_result_refs
                 WHERE parse_result_ref_id=NEW.result_ref
                   AND parse_record_id=NEW.parse_record_id;
                IF NOT FOUND OR result_row.sha256 IS DISTINCT FROM NEW.result_sha256 THEN
                    RAISE EXCEPTION 'parse result reference invalid';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_parse_record_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.doc_parse_records
        FOR EACH ROW EXECUTE FUNCTION plm.guard_parse_record()
    """)
    op.execute("""
        CREATE FUNCTION plm.guard_parse_result_ref()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            state text;
        BEGIN
            IF TG_OP<>'INSERT' THEN
                RAISE EXCEPTION 'parse result reference is retained';
            END IF;
            SELECT parse_state INTO state FROM plm.doc_parse_records
             WHERE parse_record_id=NEW.parse_record_id FOR UPDATE;
            IF NOT FOUND OR state<>'RUNNING' THEN
                RAISE EXCEPTION 'parse result owner not running';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_parse_result_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.doc_parse_result_refs
        FOR EACH ROW EXECUTE FUNCTION plm.guard_parse_result_ref()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for ParseRecord")
    bind = op.get_bind()
    if (bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_parse_records)"))
            or bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_parse_result_refs)"))):
        raise RuntimeError("ParseRecord history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_doc_parse_result_guard ON plm.doc_parse_result_refs")
    op.execute("DROP FUNCTION plm.guard_parse_result_ref()")
    op.execute("DROP TRIGGER trg_doc_parse_record_guard ON plm.doc_parse_records")
    op.execute("DROP FUNCTION plm.guard_parse_record()")
    op.drop_table("doc_parse_result_refs", schema="plm")
    op.drop_index("ix_doc_parse_records__version_created", table_name="doc_parse_records", schema="plm")
    op.drop_table("doc_parse_records", schema="plm")
