"""Open only atomic initial SolutionSection INSERT with deferred first-result closure.

Revision ID: 20261009_0148
Revises: 20261009_0147
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0148"
down_revision = "20261009_0147"
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
  ELSIF TG_TABLE_NAME='sol_sections' AND TG_OP='INSERT' THEN
    IF NEW.section_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NOT EXISTS (
         SELECT 1 FROM plm.sol_outlines o
          WHERE o.solution_outline_id=NEW.solution_outline_id
            AND o.project_id=NEW.project_id AND o.outline_state='ACTIVE'
       ) THEN RAISE EXCEPTION 'SolutionSection initial state is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_section_create_results' AND TG_OP='INSERT' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.sol_sections s
       WHERE s.solution_section_id=NEW.solution_section_id
         AND s.solution_outline_id=NEW.solution_outline_id
         AND s.project_id=NEW.project_id AND s.section_key=NEW.section_key
         AND s.created_at=NEW.created_at AND s.section_state='ACTIVE'
         AND s.lock_version=0 AND s.current_approved_version_ref IS NULL
    ) THEN RAISE EXCEPTION 'SolutionSection first result does not match root'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Solution identity operation is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_solution_section_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.sol_section_create_results r
     WHERE r.solution_section_id=NEW.solution_section_id
       AND r.solution_outline_id=NEW.solution_outline_id
       AND r.project_id=NEW.project_id AND r.section_key=NEW.section_key
       AND r.created_at=NEW.created_at
  ) THEN RAISE EXCEPTION 'SolutionSection create result is required'; END IF;
  RETURN NULL;
END; $$;
"""

_PREVIOUS = r"""
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
"""


def upgrade() -> None:
    op.execute(sa.text(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM plm.sol_sections) OR "
        "EXISTS (SELECT 1 FROM plm.sol_section_create_results) THEN "
        "RAISE EXCEPTION 'existing SolutionSection rows require audited migration'; "
        "END IF; END $$"
    ))
    op.execute(_OPEN)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_sections__create_closure "
        "AFTER INSERT ON plm.sol_sections DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_solution_section_create_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SolutionSection Owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_sections) OR "
        "EXISTS (SELECT 1 FROM plm.sol_section_create_results)"
    )).scalar_one():
        raise RuntimeError("SolutionSection history prevents Owner downgrade")
    op.execute("DROP TRIGGER trg_sol_sections__create_closure ON plm.sol_sections")
    op.execute("DROP FUNCTION plm.assert_solution_section_create_closure()")
    op.execute(_PREVIOUS)
