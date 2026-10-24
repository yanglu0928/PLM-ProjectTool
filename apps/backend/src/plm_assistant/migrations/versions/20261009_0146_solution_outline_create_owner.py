"""Open atomic INSERT-only SolutionOutline identity creation.

Revision ID: 20261009_0146
Revises: 20261009_0145
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0146"
down_revision = "20261009_0145"
branch_labels = None
depends_on = None


_OPEN = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='sol_outlines' AND TG_OP='INSERT' THEN
    IF NEW.outline_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'SolutionOutline initial state is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_outline_create_results' AND TG_OP='INSERT' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.sol_outlines o
       WHERE o.solution_outline_id=NEW.solution_outline_id
         AND o.project_id=NEW.project_id
         AND o.name=NEW.name AND o.created_at=NEW.created_at
         AND o.outline_state='ACTIVE' AND o.lock_version=0
         AND o.current_approved_version_ref IS NULL
    ) THEN RAISE EXCEPTION 'SolutionOutline first result does not match root'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Solution identity operation is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_solution_outline_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.sol_outline_create_results r
     WHERE r.solution_outline_id=NEW.solution_outline_id
       AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.created_at=NEW.created_at
  ) THEN RAISE EXCEPTION 'SolutionOutline create result is required'; END IF;
  RETURN NULL;
END; $$;
"""

_CLOSED = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Solution identity Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.execute(_OPEN)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_outlines__create_closure "
        "AFTER INSERT ON plm.sol_outlines DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_solution_outline_create_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SolutionOutline Owner downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outlines) OR "
        "EXISTS (SELECT 1 FROM plm.sol_outline_create_results)"
    )).scalar_one():
        raise RuntimeError("SolutionOutline history prevents Owner downgrade")
    op.execute("DROP TRIGGER trg_sol_outlines__create_closure ON plm.sol_outlines")
    op.execute("DROP FUNCTION plm.assert_solution_outline_create_closure()")
    op.execute(_CLOSED)
