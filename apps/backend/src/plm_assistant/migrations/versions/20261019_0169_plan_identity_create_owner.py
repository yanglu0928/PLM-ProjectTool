"""Open atomic INSERT-only Plan identity creation with first-result closure.

Revision ID: 20261019_0169
Revises: 20261019_0168
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261019_0169"
down_revision = "20261019_0168"
branch_labels = None
depends_on = None


_OPEN_ROOT = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.plan_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'Plan initial state is invalid'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Plan identity operation is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_plan_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.pln_plan_create_results r
     WHERE r.plan_id=NEW.plan_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.created_at=NEW.created_at
  ) THEN RAISE EXCEPTION 'Plan create result is required'; END IF;
  RETURN NULL;
END; $$;
"""

_OPEN_RESULT = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND EXISTS (
    SELECT 1 FROM plm.pln_plans p
     WHERE p.plan_id=NEW.plan_id AND p.project_id=NEW.project_id
       AND p.name=NEW.name AND p.created_at=NEW.created_at
       AND p.plan_state='ACTIVE' AND p.lock_version=0
       AND p.current_approved_version_ref IS NULL
  ) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'Plan create result operation is not installed';
END; $$;
"""

_CLOSED_ROOT = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan identity Owner is not installed';
END; $$;
"""

_CLOSED_RESULT = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan create result Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.execute(sa.text(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM plm.pln_plans) OR "
        "EXISTS (SELECT 1 FROM plm.pln_plan_create_results) THEN "
        "RAISE EXCEPTION 'existing Plan rows require audited migration'; "
        "END IF; END $$"
    ))
    op.execute(_OPEN_ROOT)
    op.execute(_OPEN_RESULT)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_pln_plans__create_closure "
        "AFTER INSERT ON plm.pln_plans DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_plan_create_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan create Owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_plans) OR "
        "EXISTS (SELECT 1 FROM plm.pln_plan_create_results)"
    )).scalar_one():
        raise RuntimeError("Plan history prevents create Owner downgrade")
    op.execute("DROP TRIGGER trg_pln_plans__create_closure ON plm.pln_plans")
    op.execute("DROP FUNCTION plm.assert_plan_create_closure()")
    op.execute(_CLOSED_ROOT)
    op.execute(_CLOSED_RESULT)
