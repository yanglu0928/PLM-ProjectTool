"""Add HND-03 ActionItem foundation with closed lifecycle owner.

Revision ID: 20261005_0098
Revises: 20261005_0097
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261005_0098"
down_revision = "20261005_0097"
branch_labels = None
depends_on = None

_TABLES = (
    "hnd_action_items", "hnd_action_response_refs",
    "hnd_action_evidence_refs", "hnd_action_state_events",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_handover_action_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN
    RAISE EXCEPTION 'Handover Action Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='hnd_action_items' THEN
    IF NEW.action_state<>'OPEN' OR NEW.lock_version<>0
       OR NEW.submitted_at IS NOT NULL OR NEW.verified_by IS NOT NULL
       OR NEW.verified_at IS NOT NULL OR NEW.closed_at IS NOT NULL
       OR NEW.resolution_trace_ref IS NOT NULL
       OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Handover Action initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='hnd_action_state_events' THEN
    IF NEW.sequence_no<>0 OR NEW.from_state IS NOT NULL OR NEW.to_state<>'OPEN' THEN
      RAISE EXCEPTION 'Handover Action initial event is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Handover Action lifecycle Owner is not installed';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.validate_handover_action_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target_action uuid;
  action_row plm.hnd_action_items%ROWTYPE;
  event_row plm.hnd_action_state_events%ROWTYPE;
BEGIN
  target_action := NEW.action_item_id;
  SELECT * INTO action_row FROM plm.hnd_action_items
   WHERE action_item_id=target_action;
  IF action_row.action_item_id IS NULL THEN
    RAISE EXCEPTION 'Handover Action is missing';
  END IF;
  SELECT * INTO event_row FROM plm.hnd_action_state_events
   WHERE action_item_id=target_action AND sequence_no=0;
  IF event_row.action_state_event_id IS NULL
     OR (SELECT count(*) FROM plm.hnd_action_state_events
          WHERE action_item_id=target_action)<>1
     OR event_row.project_id<>action_row.project_id
     OR event_row.from_state IS NOT NULL OR event_row.to_state<>'OPEN'
     OR event_row.actor_id<>action_row.created_by
     OR event_row.reason<>action_row.created_reason
     OR event_row.occurred_at<action_row.created_at THEN
    RAISE EXCEPTION 'Handover Action initial event is incomplete';
  END IF;
  IF action_row.due_at<action_row.created_at THEN
    RAISE EXCEPTION 'Handover Action due time precedes creation';
  END IF;
  IF action_row.source_kind='ANALYSIS_ITEM' AND NOT EXISTS (
       SELECT 1 FROM plm.hnd_analysis_items i
       JOIN plm.hnd_analysis_versions v
         ON v.handover_analysis_version_id=i.handover_analysis_version_id
        WHERE i.handover_analysis_version_id=action_row.source_analysis_version_ref
          AND i.analysis_item_id=action_row.source_item_id
          AND i.project_id=action_row.project_id
          AND ((v.version_state='DRAFT' AND i.item_state='CANDIDATE')
               OR (v.version_state='APPROVED' AND i.item_state='CONFIRMED'))) THEN
    RAISE EXCEPTION 'Handover Action source item is not eligible';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_handover_action_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Handover Action history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "hnd_action_items",
        sa.Column("action_item_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_analysis_version_ref", ident),
        sa.Column("source_item_id", ident),
        sa.Column("human_source_reason", sa.Text()),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("requested_input_spec", postgresql.JSONB(), nullable=False),
        sa.Column("owner_ref", ident, nullable=False),
        sa.Column("due_at", timestamp, nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("action_state", sa.Text(), nullable=False,
                  server_default=sa.text("'OPEN'")),
        sa.Column("submitted_at", timestamp),
        sa.Column("verified_by", ident),
        sa.Column("verified_at", timestamp),
        sa.Column("closed_at", timestamp),
        sa.Column("resolution_trace_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_reason", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("action_item_id", "project_id",
                            name="uq_hnd_actions__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_hnd_actions__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["source_analysis_version_ref", "source_item_id"],
            ["plm.hnd_analysis_items.handover_analysis_version_id",
             "plm.hnd_analysis_items.analysis_item_id"],
            name="fk_hnd_actions__source_item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["owner_ref"], ["plm.auth_users.user_id"],
                                name="fk_hnd_actions__owner", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_hnd_actions__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_hnd_actions__updater", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["verified_by"], ["plm.auth_users.user_id"],
                                name="fk_hnd_actions__verifier", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["resolution_trace_ref"], ["plm.trc_links.trace_link_id"],
                                name="fk_hnd_actions__resolution_trace", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "(source_kind='ANALYSIS_ITEM' AND source_analysis_version_ref IS NOT NULL "
            "AND source_item_id IS NOT NULL AND human_source_reason IS NULL) OR "
            "(source_kind='HUMAN' AND source_analysis_version_ref IS NULL "
            "AND source_item_id IS NULL AND human_source_reason IS NOT NULL "
            "AND char_length(human_source_reason) BETWEEN 1 AND 2000 "
            "AND human_source_reason=btrim(human_source_reason))",
            name="ck_hnd_actions__source_shape"),
        sa.CheckConstraint(
            "action_type IN ('PROVIDE_INFO','CONFIRM_DECISION','RESOLVE_CONFLICT',"
            "'MITIGATE_RISK','DEFINE_SCOPE','OTHER')",
            name="ck_hnd_actions__type"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                           name="ck_hnd_actions__title"),
        sa.CheckConstraint("jsonb_typeof(requested_input_spec)='object'",
                           name="ck_hnd_actions__input_spec"),
        sa.CheckConstraint("priority IN ('LOW','MEDIUM','HIGH','URGENT')",
                           name="ck_hnd_actions__priority"),
        sa.CheckConstraint(
            "action_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED','CLOSED','CANCELLED')",
            name="ck_hnd_actions__state"),
        sa.CheckConstraint("char_length(created_reason) BETWEEN 1 AND 2000 "
                           "AND created_reason=btrim(created_reason)",
                           name="ck_hnd_actions__created_reason"),
        sa.CheckConstraint("lock_version>=0", name="ck_hnd_actions__lock"),
        schema="plm",
    )
    op.create_index("ix_hnd_actions__project_state_due", "hnd_action_items",
                    ["project_id", "action_state", "due_at", "action_item_id"],
                    schema="plm")
    op.create_index("ix_hnd_actions__owner_state_due", "hnd_action_items",
                    ["owner_ref", "action_state", "due_at", "action_item_id"],
                    schema="plm")
    op.create_index("ix_hnd_actions__source_item", "hnd_action_items",
                    ["source_analysis_version_ref", "source_item_id"], schema="plm")
    _owned_tables(ident, timestamp)
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_handover_action_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_handover_action_truncate()"
        ))
    for table in ("hnd_action_items", "hnd_action_state_events"):
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__complete AFTER INSERT ON plm.{table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "
            "plm.validate_handover_action_foundation()"
        ))


def _owned_tables(ident, timestamp) -> None:
    action_fk = (
        ["action_item_id", "project_id"],
        ["plm.hnd_action_items.action_item_id", "plm.hnd_action_items.project_id"],
    )
    op.create_table(
        "hnd_action_response_refs",
        sa.Column("action_response_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("action_item_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("action_item_id", "document_version_id",
                            name="uq_hnd_action_responses__action_version"),
        sa.UniqueConstraint("action_item_id", "ordinal",
                            name="uq_hnd_action_responses__action_ordinal"),
        sa.ForeignKeyConstraint(*action_fk, name="fk_hnd_action_responses__action",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_hnd_action_responses__document", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_action_responses__ordinal"),
        schema="plm",
    )
    op.create_table(
        "hnd_action_evidence_refs",
        sa.Column("action_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("action_item_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("action_item_id", "evidence_id", "purpose",
                            name="uq_hnd_action_evidence__action_evidence_purpose"),
        sa.UniqueConstraint("action_item_id", "ordinal",
                            name="uq_hnd_action_evidence__action_ordinal"),
        sa.ForeignKeyConstraint(*action_fk, name="fk_hnd_action_evidence__action",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_hnd_action_evidence__evidence",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("purpose IN ('SUBMISSION','VERIFICATION','RESOLUTION')",
                           name="ck_hnd_action_evidence__purpose"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_action_evidence__ordinal"),
        schema="plm",
    )
    op.create_table(
        "hnd_action_state_events",
        sa.Column("action_state_event_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("action_item_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.Text()),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.UniqueConstraint("action_item_id", "sequence_no",
                            name="uq_hnd_action_events__action_sequence"),
        sa.ForeignKeyConstraint(*action_fk, name="fk_hnd_action_events__action",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_hnd_action_events__actor", ondelete="NO ACTION"),
        sa.CheckConstraint("sequence_no>=0", name="ck_hnd_action_events__sequence"),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state IN "
            "('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED','CLOSED','CANCELLED')",
            name="ck_hnd_action_events__from_state"),
        sa.CheckConstraint(
            "to_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED','CLOSED','CANCELLED')",
            name="ck_hnd_action_events__to_state"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
                           name="ck_hnd_action_events__reason"),
        schema="plm",
    )
    op.create_index("ix_hnd_action_events__action_occurred",
                    "hnd_action_state_events",
                    ["action_item_id", "occurred_at", "sequence_no"], schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Handover Action foundation downgrade is disabled")
    op.execute("LOCK TABLE " + ", ".join("plm." + table for table in _TABLES)
               + " IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM plm.hnd_action_items)
             OR EXISTS (SELECT 1 FROM plm.hnd_action_response_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_action_evidence_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_action_state_events) THEN
            RAISE EXCEPTION 'Handover Action history prevents downgrade';
          END IF;
        END $$;
    """)
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_handover_action_foundation()")
    op.execute("DROP FUNCTION plm.guard_handover_action_foundation()")
    op.execute("DROP FUNCTION plm.reject_handover_action_truncate()")
