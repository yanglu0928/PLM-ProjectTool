"""Add SRV-03 Survey Round and fixed field-record foundation.

Revision ID: 20261006_0107
Revises: 20261006_0106
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261006_0107"
down_revision = "20261006_0106"
branch_labels = None
depends_on = None

_TABLES = ("srv_rounds", "srv_round_source_records")

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_round_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  round_row plm.srv_rounds%ROWTYPE;
BEGIN
  IF TG_TABLE_NAME='srv_rounds' THEN
    IF TG_OP='DELETE' THEN
      RAISE EXCEPTION 'Survey Round history is immutable';
    END IF;
    IF TG_OP='INSERT' THEN
      IF NEW.round_state<>'PLANNED' OR NEW.lock_version<>0
         OR NEW.updated_by IS NOT NULL OR NEW.opened_by IS NOT NULL
         OR NEW.opened_at IS NOT NULL OR NEW.closed_by IS NOT NULL
         OR NEW.closed_at IS NOT NULL OR NEW.close_report_fingerprint IS NOT NULL
         OR NEW.cancelled_by IS NOT NULL OR NEW.cancelled_at IS NOT NULL
         OR NEW.cancellation_reason IS NOT NULL THEN
        RAISE EXCEPTION 'Survey Round initial state is invalid';
      END IF;
      IF NOT EXISTS (
           SELECT 1 FROM plm.srv_surveys s
           JOIN plm.srv_survey_versions v
             ON v.survey_version_id=NEW.survey_version_id
            AND v.survey_id=s.survey_id AND v.project_id=s.project_id
            WHERE s.survey_id=NEW.survey_id AND s.project_id=NEW.project_id
              AND s.survey_state='ACTIVE'
              AND s.current_approved_version_ref=NEW.survey_version_id
              AND v.version_state='APPROVED') THEN
        RAISE EXCEPTION 'Survey Round requires the current approved definition';
      END IF;
      RETURN NEW;
    END IF;
    IF ROW(NEW.survey_round_id,NEW.survey_id,NEW.survey_version_id,
           NEW.project_id,NEW.round_no,NEW.created_by,NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.survey_round_id,OLD.survey_id,OLD.survey_version_id,
           OLD.project_id,OLD.round_no,OLD.created_by,OLD.created_at)
       OR NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_by IS NULL
       OR NEW.updated_at<OLD.updated_at OR NEW.updated_at<NEW.created_at THEN
      RAISE EXCEPTION 'Survey Round update projection is invalid';
    END IF;
    IF OLD.round_state='PLANNED' AND NEW.round_state='PLANNED' THEN
      IF ROW(NEW.opened_by,NEW.opened_at,NEW.closed_by,NEW.closed_at,
             NEW.close_report_fingerprint,NEW.cancelled_by,NEW.cancelled_at,
             NEW.cancellation_reason)
         IS DISTINCT FROM
         ROW(OLD.opened_by,OLD.opened_at,OLD.closed_by,OLD.closed_at,
             OLD.close_report_fingerprint,OLD.cancelled_by,OLD.cancelled_at,
             OLD.cancellation_reason) THEN
        RAISE EXCEPTION 'Survey Round schedule update is invalid';
      END IF;
    ELSIF OLD.round_state='PLANNED' AND NEW.round_state='OPEN' THEN
      IF ROW(NEW.scheduled_start_at,NEW.scheduled_end_at,NEW.location_note,
             NEW.closed_by,NEW.closed_at,NEW.close_report_fingerprint,
             NEW.cancelled_by,NEW.cancelled_at,NEW.cancellation_reason)
         IS DISTINCT FROM
         ROW(OLD.scheduled_start_at,OLD.scheduled_end_at,OLD.location_note,
             OLD.closed_by,OLD.closed_at,OLD.close_report_fingerprint,
             OLD.cancelled_by,OLD.cancelled_at,OLD.cancellation_reason)
         OR NEW.opened_by IS DISTINCT FROM NEW.updated_by
         OR NEW.opened_at IS DISTINCT FROM NEW.updated_at
         OR NOT EXISTS (
           SELECT 1 FROM plm.srv_surveys s
           JOIN plm.srv_survey_versions v
             ON v.survey_version_id=NEW.survey_version_id
            AND v.survey_id=s.survey_id AND v.project_id=s.project_id
            WHERE s.survey_id=NEW.survey_id AND s.project_id=NEW.project_id
              AND s.survey_state='ACTIVE'
              AND s.current_approved_version_ref=NEW.survey_version_id
              AND v.version_state='APPROVED') THEN
        RAISE EXCEPTION 'Survey Round open projection is invalid';
      END IF;
    ELSIF OLD.round_state='OPEN' AND NEW.round_state='CLOSED' THEN
      IF ROW(NEW.scheduled_start_at,NEW.scheduled_end_at,NEW.location_note,
             NEW.opened_by,NEW.opened_at,NEW.cancelled_by,NEW.cancelled_at,
             NEW.cancellation_reason)
         IS DISTINCT FROM
         ROW(OLD.scheduled_start_at,OLD.scheduled_end_at,OLD.location_note,
             OLD.opened_by,OLD.opened_at,OLD.cancelled_by,OLD.cancelled_at,
             OLD.cancellation_reason)
         OR NEW.closed_by IS DISTINCT FROM NEW.updated_by
         OR NEW.closed_at IS DISTINCT FROM NEW.updated_at
         OR NEW.close_report_fingerprint IS NULL THEN
        RAISE EXCEPTION 'Survey Round close projection is invalid';
      END IF;
    ELSIF OLD.round_state='PLANNED' AND NEW.round_state='CANCELLED' THEN
      IF ROW(NEW.scheduled_start_at,NEW.scheduled_end_at,NEW.location_note,
             NEW.opened_by,NEW.opened_at,NEW.closed_by,NEW.closed_at,
             NEW.close_report_fingerprint)
         IS DISTINCT FROM
         ROW(OLD.scheduled_start_at,OLD.scheduled_end_at,OLD.location_note,
             OLD.opened_by,OLD.opened_at,OLD.closed_by,OLD.closed_at,
             OLD.close_report_fingerprint)
         OR NEW.cancelled_by IS DISTINCT FROM NEW.updated_by
         OR NEW.cancelled_at IS DISTINCT FROM NEW.updated_at
         OR NEW.cancellation_reason IS NULL THEN
        RAISE EXCEPTION 'Survey Round cancel projection is invalid';
      END IF;
    ELSE
      RAISE EXCEPTION 'Survey Round state transition is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Survey Round source record is immutable';
  END IF;
  SELECT * INTO round_row FROM plm.srv_rounds
   WHERE survey_round_id=NEW.survey_round_id FOR SHARE;
  IF round_row.survey_round_id IS NULL OR round_row.round_state<>'OPEN'
     OR ROW(NEW.survey_id,NEW.survey_version_id,NEW.project_id)
        IS DISTINCT FROM
        ROW(round_row.survey_id,round_row.survey_version_id,round_row.project_id) THEN
    RAISE EXCEPTION 'Survey Round source requires an open matching Round';
  END IF;
  IF NOT EXISTS (
       SELECT 1 FROM plm.evd_evidence_records e
       JOIN plm.doc_document_versions v
         ON v.document_version_id=e.document_version_id
        AND v.document_id=e.document_id
       JOIN plm.doc_documents d ON d.document_id=v.document_id
       WHERE e.evidence_id=NEW.evidence_id AND e.scope='PROJECT'
         AND e.project_id=NEW.project_id AND e.eligibility_state='ELIGIBLE'
         AND e.lock_version=NEW.observed_evidence_lock_version
         AND e.content_fingerprint=NEW.content_fingerprint
         AND e.document_id=NEW.document_id
         AND e.document_version_id=NEW.document_version_id
         AND v.scope='PROJECT' AND v.project_id=NEW.project_id
         AND v.availability_state='AVAILABLE'
         AND d.scope='PROJECT' AND d.project_id=NEW.project_id
         AND d.document_state='ACTIVE' AND d.document_category='PROJECT_RECORD') THEN
    RAISE EXCEPTION 'Survey Round source is not an eligible PROJECT_RECORD';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_survey_round_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Survey Round history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "srv_rounds",
        sa.Column("survey_round_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("round_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PLANNED'")),
        sa.Column("scheduled_start_at", timestamp),
        sa.Column("scheduled_end_at", timestamp),
        sa.Column("location_note", sa.Text()),
        sa.Column("opened_by", ident),
        sa.Column("opened_at", timestamp),
        sa.Column("closed_by", ident),
        sa.Column("closed_at", timestamp),
        sa.Column("close_report_fingerprint", sa.LargeBinary()),
        sa.Column("cancelled_by", ident),
        sa.Column("cancelled_at", timestamp),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("survey_round_id", "survey_version_id", "survey_id",
                            "project_id", name="uq_srv_rounds__identity"),
        sa.UniqueConstraint("survey_id", "round_no", name="uq_srv_rounds__survey_no"),
        sa.ForeignKeyConstraint(
            ["survey_version_id", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_rounds__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_rounds__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_rounds__updater", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["opened_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_rounds__opener", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["closed_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_rounds__closer", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_rounds__canceller", ondelete="NO ACTION"),
        sa.CheckConstraint("round_no>0", name="ck_srv_rounds__number"),
        sa.CheckConstraint("round_state IN ('PLANNED','OPEN','CLOSED','CANCELLED')",
                           name="ck_srv_rounds__state"),
        sa.CheckConstraint(
            "(scheduled_start_at IS NULL AND scheduled_end_at IS NULL) OR "
            "(scheduled_start_at IS NOT NULL AND scheduled_end_at IS NOT NULL "
            "AND scheduled_end_at>scheduled_start_at)",
            name="ck_srv_rounds__schedule"),
        sa.CheckConstraint(
            "location_note IS NULL OR (char_length(location_note) BETWEEN 1 AND 1000 "
            "AND location_note=btrim(location_note))",
            name="ck_srv_rounds__location"),
        sa.CheckConstraint(
            "(round_state='PLANNED' AND opened_by IS NULL AND opened_at IS NULL "
            "AND closed_by IS NULL AND closed_at IS NULL "
            "AND close_report_fingerprint IS NULL AND cancelled_by IS NULL "
            "AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR "
            "(round_state='OPEN' AND opened_by IS NOT NULL AND opened_at IS NOT NULL "
            "AND closed_by IS NULL AND closed_at IS NULL "
            "AND close_report_fingerprint IS NULL AND cancelled_by IS NULL "
            "AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR "
            "(round_state='CLOSED' AND opened_by IS NOT NULL AND opened_at IS NOT NULL "
            "AND closed_by IS NOT NULL AND closed_at IS NOT NULL "
            "AND close_report_fingerprint IS NOT NULL "
            "AND octet_length(close_report_fingerprint)=32 "
            "AND cancelled_by IS NULL AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL AND closed_at>=opened_at) OR "
            "(round_state='CANCELLED' AND opened_by IS NULL AND opened_at IS NULL "
            "AND closed_by IS NULL AND closed_at IS NULL "
            "AND close_report_fingerprint IS NULL AND cancelled_by IS NOT NULL "
            "AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL "
            "AND char_length(cancellation_reason) BETWEEN 1 AND 2000 "
            "AND cancellation_reason=btrim(cancellation_reason) "
            "AND cancelled_at>=created_at)",
            name="ck_srv_rounds__lifecycle"),
        sa.CheckConstraint("lock_version>=0", name="ck_srv_rounds__lock"),
        schema="plm",
    )
    op.create_index("ix_srv_rounds__project_state_schedule", "srv_rounds",
                    ["project_id", "round_state", "scheduled_start_at",
                     "survey_round_id"], schema="plm")
    op.create_index("ix_srv_rounds__survey_number", "srv_rounds",
                    ["survey_id", "round_no"], schema="plm")
    op.create_table(
        "srv_round_source_records",
        sa.Column("round_source_record_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("survey_round_id", ident, nullable=False),
        sa.Column("survey_id", ident, nullable=False),
        sa.Column("survey_version_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("question_row_id", ident),
        sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("observed_evidence_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("recorded_by", ident, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("survey_round_id", "ordinal",
                            name="uq_srv_round_sources__round_ordinal"),
        sa.UniqueConstraint(
            "survey_round_id", "question_row_id", "evidence_id",
            name="uq_srv_round_sources__round_question_evidence",
            postgresql_nulls_not_distinct=True),
        sa.ForeignKeyConstraint(
            ["survey_round_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_rounds.survey_round_id", "plm.srv_rounds.survey_version_id",
             "plm.srv_rounds.survey_id", "plm.srv_rounds.project_id"],
            name="fk_srv_round_sources__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id", "plm.srv_questions.survey_id",
             "plm.srv_questions.project_id"],
            name="fk_srv_round_sources__question", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_round_sources__document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_srv_round_sources__evidence", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["recorded_by"], ["plm.auth_users.user_id"],
                                name="fk_srv_round_sources__recorder", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_srv_round_sources__ordinal"),
        sa.CheckConstraint("observed_evidence_lock_version>=0",
                           name="ck_srv_round_sources__evidence_lock"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_srv_round_sources__fingerprint"),
        sa.CheckConstraint("recorded_at<=created_at",
                           name="ck_srv_round_sources__recorded_at"),
        schema="plm",
    )
    op.create_index("ix_srv_round_sources__evidence", "srv_round_source_records",
                    ["evidence_id", "survey_round_id"], schema="plm")
    op.create_index("ix_srv_round_sources__question", "srv_round_source_records",
                    ["question_row_id", "survey_round_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_survey_round_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_survey_round_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Survey Round downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(
                f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Survey Round history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_survey_round_foundation()")
    op.execute("DROP FUNCTION plm.reject_survey_round_truncate()")
