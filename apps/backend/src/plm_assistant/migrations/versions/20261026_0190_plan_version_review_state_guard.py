"""Bind PlanVersion Review state transitions to immutable real Review results.

Revision ID: 20261026_0190
Revises: 20261026_0189
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261026_0190"
down_revision = "20261026_0189"
branch_labels = None
depends_on = None

_TABLE = "pln_plan_version_review_state_results"

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_version_review_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref'])
       IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['version_state','review_ref','review_round_ref'])
     OR NOT (
       (OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'
        AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
        AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
       OR (OLD.version_state='IN_REVIEW'
           AND NEW.version_state IN ('APPROVED','RETURNED')
           AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
           AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
       OR (OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
           AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
           AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
     ) THEN
    RAISE EXCEPTION 'PlanVersion update is outside Review Owner';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_plan_version_review_state_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_row plm.pln_plan_versions%ROWTYPE;
        review_row plm.rvw_reviews%ROWTYPE;
        round_row plm.rvw_review_rounds%ROWTYPE;
        expected_state text;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'PlanVersion Review state history is immutable';
  END IF;
  SELECT * INTO version_row FROM plm.pln_plan_versions
   WHERE plan_version_id=NEW.plan_version_id AND plan_id=NEW.plan_id
     AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_id FOR SHARE;
  expected_state := CASE NEW.event_type
    WHEN 'START' THEN 'IN_REVIEW'
    WHEN 'APPROVED' THEN 'APPROVED'
    WHEN 'RETURNED' THEN 'RETURNED'
    WHEN 'SUPERSEDED' THEN 'SUPERSEDED'
    ELSE NULL END;
  IF expected_state IS NULL
     OR version_row.plan_version_id IS NULL
     OR version_row.version_state IS DISTINCT FROM NEW.current_state
     OR version_row.review_ref IS DISTINCT FROM NEW.review_id
     OR version_row.review_round_ref IS DISTINCT FROM NEW.review_round_id
     OR NEW.current_state IS DISTINCT FROM expected_state
     OR review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'PLN-02'
     OR review_row.subject_id IS DISTINCT FROM NEW.plan_version_id
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_id
     OR round_row.scope<>'PROJECT'
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.plan_version_id
     OR NOT (
       (NEW.event_type='START' AND NEW.previous_state='DRAFT'
        AND review_row.review_state='IN_REVIEW'
        AND review_row.active_round_id=NEW.review_round_id
        AND round_row.round_state='IN_REVIEW'
        AND round_row.started_by=NEW.actor_id
        AND EXISTS (SELECT 1 FROM plm.rvw_round_events e
          WHERE e.review_id=NEW.review_id AND e.review_round_id=NEW.review_round_id
            AND e.actor_id=NEW.actor_id AND e.event_type='STARTED'
            AND e.result_state='IN_REVIEW'))
       OR (NEW.event_type IN ('APPROVED','RETURNED')
        AND NEW.previous_state='IN_REVIEW'
        AND review_row.review_state=NEW.event_type
        AND review_row.active_round_id IS NULL
        AND round_row.round_state=NEW.event_type
        AND EXISTS (SELECT 1 FROM plm.rvw_round_events e
          WHERE e.review_id=NEW.review_id AND e.review_round_id=NEW.review_round_id
            AND e.actor_id=NEW.actor_id AND e.result_state=NEW.event_type))
       OR (NEW.event_type='SUPERSEDED' AND NEW.previous_state='APPROVED'
        AND review_row.review_state='APPROVED'
        AND round_row.round_state='APPROVED'
        AND EXISTS (SELECT 1 FROM plm.rvw_round_events e
          WHERE e.review_id=NEW.review_id AND e.review_round_id=NEW.review_round_id
            AND e.actor_id=NEW.actor_id AND e.result_state='APPROVED'))
     ) THEN
    RAISE EXCEPTION 'PlanVersion Review result does not match current facts';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_plan_version_review_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results r
      WHERE r.plan_version_id=NEW.plan_version_id AND r.plan_id=NEW.plan_id
        AND r.project_id=NEW.project_id AND r.review_id=NEW.review_ref
        AND r.review_round_id=NEW.review_round_ref
        AND r.previous_state=OLD.version_state
        AND r.current_state=NEW.version_state
        AND r.event_type=CASE NEW.version_state
          WHEN 'IN_REVIEW' THEN 'START'
          WHEN 'APPROVED' THEN 'APPROVED'
          WHEN 'RETURNED' THEN 'RETURNED'
          WHEN 'SUPERSEDED' THEN 'SUPERSEDED'
          ELSE NULL END)
    THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'PlanVersion Review transition has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plan_version_review_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PlanVersion Review history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode():
        op.execute("LOCK TABLE plm.pln_plan_versions IN ACCESS EXCLUSIVE MODE")
        if op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm.pln_plan_versions "
            "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
            "OR review_round_ref IS NOT NULL)"
        )).scalar_one():
            raise RuntimeError("pre-existing Plan Review state requires audited migration")
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        _TABLE,
        sa.Column("review_state_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("review_id", ident, nullable=False),
        sa.Column("review_round_id", ident, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("previous_state", sa.Text(), nullable=False),
        sa.Column("current_state", sa.Text(), nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("plan_version_id", "event_type",
                            name="uq_pln_plan_review_results__version_event"),
        sa.UniqueConstraint("review_id", "review_round_id", "event_type",
                            name="uq_pln_plan_review_results__round_event"),
        sa.ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_plan_review_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_id"], ["plm.rvw_reviews.review_id"],
                                name="fk_pln_plan_review_results__review",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_id"],
                                ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_pln_plan_review_results__round",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_pln_plan_review_results__actor",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("event_type IN ('START','APPROVED','RETURNED','SUPERSEDED')",
                           name="ck_pln_plan_review_results__event"),
        sa.CheckConstraint(
            "(event_type='START' AND previous_state='DRAFT' AND current_state='IN_REVIEW') "
            "OR (event_type='APPROVED' AND previous_state='IN_REVIEW' AND current_state='APPROVED') "
            "OR (event_type='RETURNED' AND previous_state='IN_REVIEW' AND current_state='RETURNED') "
            "OR (event_type='SUPERSEDED' AND previous_state='APPROVED' AND current_state='SUPERSEDED')",
            name="ck_pln_plan_review_results__transition"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_pln_plan_review_results__created_at"),
        schema="plm",
    )
    op.create_index("ix_pln_plan_review_results__review_round", _TABLE,
                    ["review_id", "review_round_id"], schema="plm")
    op.execute(sa.text(_GUARDS))
    op.execute("DROP TRIGGER trg_pln_plan_versions__owner ON plm.pln_plan_versions")
    op.execute(
        "CREATE TRIGGER trg_pln_plan_versions__owner "
        "BEFORE INSERT OR DELETE ON plm.pln_plan_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_version_foundation()")
    op.execute(
        "CREATE TRIGGER trg_pln_plan_versions__review_update "
        "BEFORE UPDATE ON plm.pln_plan_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_version_review_transition()")
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}__owner BEFORE INSERT OR UPDATE OR DELETE "
        f"ON plm.{_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_version_review_state_result()")
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}__no_truncate BEFORE TRUNCATE ON plm.{_TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plan_version_review_result_truncate()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_pln_plan_versions__review_closure "
        "AFTER UPDATE ON plm.pln_plan_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_plan_version_review_closure()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan Review state downgrade is disabled")
    op.execute("LOCK TABLE plm.pln_plan_versions, "
               f"plm.{_TABLE} IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{_TABLE}) OR "
        "EXISTS (SELECT 1 FROM plm.pln_plan_versions "
        "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
        "OR review_round_ref IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Plan Review state history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_plan_versions__review_closure "
               "ON plm.pln_plan_versions")
    op.execute("DROP TRIGGER trg_pln_plan_versions__review_update "
               "ON plm.pln_plan_versions")
    op.execute("DROP TRIGGER trg_pln_plan_versions__owner ON plm.pln_plan_versions")
    op.execute(
        "CREATE TRIGGER trg_pln_plan_versions__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.pln_plan_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_version_foundation()")
    op.execute(f"DROP TRIGGER trg_{_TABLE}__owner ON plm.{_TABLE}")
    op.execute(f"DROP TRIGGER trg_{_TABLE}__no_truncate ON plm.{_TABLE}")
    op.drop_index("ix_pln_plan_review_results__review_round", table_name=_TABLE,
                  schema="plm")
    op.drop_table(_TABLE, schema="plm")
    for name in ("guard_plan_version_review_transition",
                 "guard_plan_version_review_state_result",
                 "enforce_plan_version_review_closure",
                 "reject_plan_version_review_result_truncate"):
        op.execute(f"DROP FUNCTION plm.{name}()")
