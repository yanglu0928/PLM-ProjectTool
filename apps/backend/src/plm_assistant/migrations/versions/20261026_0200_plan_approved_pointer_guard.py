"""Bind the Plan Approved pointer to unique 0190 Review lifecycle facts.

Revision ID: 20261026_0200
Revises: 20261026_0190
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261026_0200"
down_revision = "20261026_0190"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.plan_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'Plan initial state is invalid';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP <> 'UPDATE'
     OR (to_jsonb(NEW)-ARRAY['current_approved_version_ref','lock_version'])
          IS DISTINCT FROM
        (to_jsonb(OLD)-ARRAY['current_approved_version_ref','lock_version'])
     OR NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref
     OR NEW.lock_version <> OLD.lock_version + 1 THEN
    RAISE EXCEPTION 'Plan identity update is outside Approved Review Owner';
  END IF;
  IF NEW.current_approved_version_ref IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM plm.pln_plan_versions v
       WHERE v.plan_version_id=NEW.current_approved_version_ref
         AND v.plan_id=NEW.plan_id AND v.project_id=NEW.project_id
         AND v.version_state='APPROVED') THEN
    RAISE EXCEPTION 'Plan Approved pointer target is not current';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_plan_approved_pointer_consistency()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_plan uuid;
        target_project uuid;
        approved_pointer uuid;
        approved_version uuid;
        approved_count bigint;
BEGIN
  target_plan := NEW.plan_id;
  target_project := NEW.project_id;
  SELECT current_approved_version_ref INTO approved_pointer
    FROM plm.pln_plans
   WHERE plan_id=target_plan AND project_id=target_project;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Plan Approved pointer owner is unavailable';
  END IF;
  SELECT count(*), (array_agg(plan_version_id ORDER BY version_no DESC))[1]
    INTO approved_count, approved_version
    FROM plm.pln_plan_versions
   WHERE plan_id=target_plan AND project_id=target_project
     AND version_state='APPROVED';
  IF approved_count > 1 OR approved_pointer IS DISTINCT FROM approved_version THEN
    RAISE EXCEPTION 'Plan Approved pointer does not match unique Approved version';
  END IF;

  IF TG_TABLE_NAME='pln_plans' THEN
    IF NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref THEN
      IF NEW.current_approved_version_ref IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results r
           WHERE r.plan_version_id=NEW.current_approved_version_ref
             AND r.plan_id=target_plan AND r.project_id=target_project
             AND r.event_type='APPROVED' AND r.previous_state='IN_REVIEW'
             AND r.current_state='APPROVED') THEN
        RAISE EXCEPTION 'Plan Approved pointer has no matching 0190 result';
      END IF;
      IF OLD.current_approved_version_ref IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results r
           WHERE r.plan_version_id=OLD.current_approved_version_ref
             AND r.plan_id=target_plan AND r.project_id=target_project
             AND r.event_type='SUPERSEDED' AND r.previous_state='APPROVED'
             AND r.current_state='SUPERSEDED') THEN
        RAISE EXCEPTION 'Previous Plan Approved pointer has no SUPERSEDED result';
      END IF;
    END IF;
  END IF;
  RETURN NULL;
END; $$;

"""


_CLOSED_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan identity Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode():
        op.execute("LOCK TABLE plm.pln_plans, plm.pln_plan_versions, "
                   "plm.pln_plan_version_review_state_results IN ACCESS EXCLUSIVE MODE")
        if op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm.pln_plans "
            "WHERE current_approved_version_ref IS NOT NULL) OR "
            "EXISTS (SELECT 1 FROM plm.pln_plan_versions "
            "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
            "OR review_round_ref IS NOT NULL) OR "
            "EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results)"
        )).scalar_one():
            raise RuntimeError("Plan Approved pointer history requires audited migration")
    op.drop_constraint(
        "ck_pln_plans__approved_pointer_closed", "pln_plans", schema="plm",
        type_="check")
    op.execute(sa.text(_GUARDS))
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_pln_plans__approved_pointer_closure "
        "AFTER UPDATE ON plm.pln_plans DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_plan_approved_pointer_consistency()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_pln_plan_versions__approved_pointer_closure "
        "AFTER UPDATE ON plm.pln_plan_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_plan_approved_pointer_consistency()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_pln_plan_review_results__approved_pointer_closure "
        "AFTER INSERT ON plm.pln_plan_version_review_state_results "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.enforce_plan_approved_pointer_consistency()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan Approved pointer downgrade is disabled")
    op.execute("LOCK TABLE plm.pln_plans, plm.pln_plan_versions, "
               "plm.pln_plan_version_review_state_results IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_plans "
        "WHERE current_approved_version_ref IS NOT NULL) OR "
        "EXISTS (SELECT 1 FROM plm.pln_plan_versions "
        "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
        "OR review_round_ref IS NOT NULL) OR "
        "EXISTS (SELECT 1 FROM plm.pln_plan_version_review_state_results)"
    )).scalar_one():
        raise RuntimeError("Plan Approved pointer history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_plans__approved_pointer_closure ON plm.pln_plans")
    op.execute("DROP TRIGGER trg_pln_plan_versions__approved_pointer_closure "
               "ON plm.pln_plan_versions")
    op.execute("DROP TRIGGER trg_pln_plan_review_results__approved_pointer_closure "
               "ON plm.pln_plan_version_review_state_results")
    op.execute("DROP FUNCTION plm.enforce_plan_approved_pointer_consistency()")
    op.execute(sa.text(_CLOSED_GUARD))
    op.create_check_constraint(
        "ck_pln_plans__approved_pointer_closed", "pln_plans",
        "current_approved_version_ref IS NULL", schema="plm")
