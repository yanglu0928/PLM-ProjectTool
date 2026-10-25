"""Represent a real Plan Review withdrawal without falsifying Plan state facts.

Revision ID: 20261026_0210
Revises: 20261026_0200
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261026_0210"
down_revision = "20261026_0200"
branch_labels = None
depends_on = None

_TABLE = "pln_plan_version_review_state_results"

_GUARDS = r"""
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
    WHEN 'WITHDRAWN' THEN 'RETURNED'
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
       OR (NEW.event_type IN ('APPROVED','RETURNED','WITHDRAWN')
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
          WHEN 'RETURNED' THEN CASE
            WHEN EXISTS (SELECT 1 FROM plm.rvw_reviews rv
                         WHERE rv.review_id=r.review_id AND rv.review_state='WITHDRAWN')
            THEN 'WITHDRAWN' ELSE 'RETURNED' END
          WHEN 'SUPERSEDED' THEN 'SUPERSEDED'
          ELSE NULL END)
    THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'PlanVersion Review transition has no immutable result';
END; $$;
"""


_DOWN_GUARDS = r"""
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
  SELECT * INTO review_row FROM plm.rvw_reviews WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds WHERE review_round_id=NEW.review_round_id FOR SHARE;
  expected_state := CASE NEW.event_type WHEN 'START' THEN 'IN_REVIEW'
    WHEN 'APPROVED' THEN 'APPROVED' WHEN 'RETURNED' THEN 'RETURNED'
    WHEN 'SUPERSEDED' THEN 'SUPERSEDED' ELSE NULL END;
  IF expected_state IS NULL OR version_row.plan_version_id IS NULL
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
        AND round_row.round_state='IN_REVIEW' AND round_row.started_by=NEW.actor_id
        AND EXISTS (SELECT 1 FROM plm.rvw_round_events e WHERE e.review_id=NEW.review_id
          AND e.review_round_id=NEW.review_round_id AND e.actor_id=NEW.actor_id
          AND e.event_type='STARTED' AND e.result_state='IN_REVIEW'))
       OR (NEW.event_type IN ('APPROVED','RETURNED')
        AND NEW.previous_state='IN_REVIEW' AND review_row.review_state=NEW.event_type
        AND review_row.active_round_id IS NULL AND round_row.round_state=NEW.event_type
        AND EXISTS (SELECT 1 FROM plm.rvw_round_events e WHERE e.review_id=NEW.review_id
          AND e.review_round_id=NEW.review_round_id AND e.actor_id=NEW.actor_id
          AND e.result_state=NEW.event_type))
       OR (NEW.event_type='SUPERSEDED' AND NEW.previous_state='APPROVED'
        AND review_row.review_state='APPROVED' AND round_row.round_state='APPROVED'
        AND EXISTS (SELECT 1 FROM plm.rvw_round_events e WHERE e.review_id=NEW.review_id
          AND e.review_round_id=NEW.review_round_id AND e.actor_id=NEW.actor_id
          AND e.result_state='APPROVED'))
     ) THEN RAISE EXCEPTION 'PlanVersion Review result does not match current facts'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_plan_version_review_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results r
      WHERE r.plan_version_id=NEW.plan_version_id AND r.plan_id=NEW.plan_id
        AND r.project_id=NEW.project_id AND r.review_id=NEW.review_ref
        AND r.review_round_id=NEW.review_round_ref
        AND r.previous_state=OLD.version_state AND r.current_state=NEW.version_state
        AND r.event_type=CASE NEW.version_state WHEN 'IN_REVIEW' THEN 'START'
          WHEN 'APPROVED' THEN 'APPROVED' WHEN 'RETURNED' THEN 'RETURNED'
          WHEN 'SUPERSEDED' THEN 'SUPERSEDED' ELSE NULL END)
    THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'PlanVersion Review transition has no immutable result';
END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode():
        op.execute("LOCK TABLE plm.pln_plan_versions, plm.pln_plan_version_review_state_results, "
                   "plm.rvw_reviews, plm.rvw_review_rounds, plm.rvw_round_events "
                   "IN ACCESS EXCLUSIVE MODE")
        if op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm.pln_plan_versions v "
            "JOIN plm.rvw_reviews r ON r.review_id=v.review_ref "
            "WHERE r.review_state='WITHDRAWN' AND r.subject_type='PLN-02' "
            "AND r.subject_id=v.plan_version_id)"
        )).scalar_one():
            raise RuntimeError("existing withdrawn Plan Review requires audited migration")
    op.drop_constraint("ck_pln_plan_review_results__event", _TABLE,
                       schema="plm", type_="check")
    op.drop_constraint("ck_pln_plan_review_results__transition", _TABLE,
                       schema="plm", type_="check")
    op.create_check_constraint(
        "ck_pln_plan_review_results__event", _TABLE,
        "event_type IN ('START','APPROVED','RETURNED','WITHDRAWN','SUPERSEDED')",
        schema="plm")
    op.create_check_constraint(
        "ck_pln_plan_review_results__transition", _TABLE,
        "(event_type='START' AND previous_state='DRAFT' AND current_state='IN_REVIEW') "
        "OR (event_type='APPROVED' AND previous_state='IN_REVIEW' AND current_state='APPROVED') "
        "OR (event_type='RETURNED' AND previous_state='IN_REVIEW' AND current_state='RETURNED') "
        "OR (event_type='WITHDRAWN' AND previous_state='IN_REVIEW' AND current_state='RETURNED') "
        "OR (event_type='SUPERSEDED' AND previous_state='APPROVED' AND current_state='SUPERSEDED')",
        schema="plm")
    op.execute(sa.text(_GUARDS))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan Review withdrawal downgrade is disabled")
    op.execute("LOCK TABLE plm.pln_plan_versions, plm.pln_plan_version_review_state_results, "
               "plm.rvw_reviews IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results "
        "WHERE event_type='WITHDRAWN') OR EXISTS ("
        "SELECT 1 FROM plm.pln_plan_versions v JOIN plm.rvw_reviews r "
        "ON r.review_id=v.review_ref WHERE r.review_state='WITHDRAWN' "
        "AND r.subject_type='PLN-02' AND r.subject_id=v.plan_version_id)"
    )).scalar_one():
        raise RuntimeError("withdrawn Plan Review history prevents downgrade")
    op.drop_constraint("ck_pln_plan_review_results__event", _TABLE,
                       schema="plm", type_="check")
    op.drop_constraint("ck_pln_plan_review_results__transition", _TABLE,
                       schema="plm", type_="check")
    op.create_check_constraint(
        "ck_pln_plan_review_results__event", _TABLE,
        "event_type IN ('START','APPROVED','RETURNED','SUPERSEDED')",
        schema="plm")
    op.create_check_constraint(
        "ck_pln_plan_review_results__transition", _TABLE,
        "(event_type='START' AND previous_state='DRAFT' AND current_state='IN_REVIEW') "
        "OR (event_type='APPROVED' AND previous_state='IN_REVIEW' AND current_state='APPROVED') "
        "OR (event_type='RETURNED' AND previous_state='IN_REVIEW' AND current_state='RETURNED') "
        "OR (event_type='SUPERSEDED' AND previous_state='APPROVED' AND current_state='SUPERSEDED')",
        schema="plm")
    op.execute(sa.text(_DOWN_GUARDS))
