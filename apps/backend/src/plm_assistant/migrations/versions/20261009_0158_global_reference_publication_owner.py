"""Allow only ordered, current-version GLOBAL publication event inserts.

Revision ID: 20261009_0158
Revises: 20261009_0157
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0158"
down_revision = "20261009_0157"
branch_labels = None
depends_on = None

_OWNER_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_global_reference_publication_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  root_row plm.sol_reference_solutions%ROWTYPE;
  prior_row plm.sol_global_reference_publication_events%ROWTYPE;
  eligibility_row plm.sol_reference_eligibility_events%ROWTYPE;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'GLOBAL Reference publication history is immutable';
  END IF;
  SELECT * INTO root_row FROM plm.sol_reference_solutions
   WHERE reference_solution_id=NEW.reference_solution_id
     AND scope='GLOBAL' AND project_id IS NULL FOR UPDATE;
  IF NOT FOUND OR root_row.current_version_ref<>NEW.reference_version_id
     OR NEW.scope<>'GLOBAL' THEN
    RAISE EXCEPTION 'GLOBAL Reference publication current version mismatch';
  END IF;
  SELECT * INTO prior_row FROM plm.sol_global_reference_publication_events
   WHERE reference_solution_id=NEW.reference_solution_id
   ORDER BY event_no DESC LIMIT 1;
  IF NEW.event_no<>COALESCE(prior_row.event_no,0)+1 THEN
    RAISE EXCEPTION 'GLOBAL Reference publication event number mismatch';
  END IF;
  IF NEW.event_kind='PUBLISH' THEN
    SELECT * INTO eligibility_row FROM plm.sol_reference_eligibility_events
     WHERE reference_solution_id=NEW.reference_solution_id
     ORDER BY result_lock_version DESC LIMIT 1;
    IF root_row.eligibility_state<>'ELIGIBLE'
       OR eligibility_row.eligibility_event_id IS NULL
       OR eligibility_row.event_kind<>'HUMAN'
       OR eligibility_row.reference_version_id<>NEW.reference_version_id
       OR eligibility_row.scope<>'GLOBAL' OR eligibility_row.project_id IS NOT NULL
       OR eligibility_row.result_state<>'ELIGIBLE'
       OR eligibility_row.result_lock_version<>root_row.lock_version
       OR (prior_row.event_kind='PUBLISH'
           AND prior_row.reference_version_id=NEW.reference_version_id) THEN
      RAISE EXCEPTION 'GLOBAL Reference publication requires current eligibility and unpublished version';
    END IF;
  ELSIF NEW.event_kind='REVOKE' THEN
    IF prior_row.event_kind IS DISTINCT FROM 'PUBLISH'
       OR prior_row.reference_version_id<>NEW.reference_version_id THEN
      RAISE EXCEPTION 'GLOBAL Reference publication revoke requires current publish';
    END IF;
  ELSE
    RAISE EXCEPTION 'GLOBAL Reference publication kind invalid';
  END IF;
  RETURN NEW;
END; $$;
"""

_CLOSED_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_global_reference_publication_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'GLOBAL Reference publication Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.execute(_OWNER_GUARD)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline GLOBAL Reference publication Owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_global_reference_publication_events)"
    )).scalar_one():
        raise RuntimeError("GLOBAL Reference publication history prevents Owner downgrade")
    op.execute(_CLOSED_GUARD)
