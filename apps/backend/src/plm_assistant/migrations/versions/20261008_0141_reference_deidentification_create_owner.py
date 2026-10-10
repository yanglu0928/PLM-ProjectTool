"""Open INSERT only for the Solution confirmation Owner; retain immutable history.

Revision ID: 20261008_0141
Revises: 20261008_0140
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261008_0141"
down_revision = "20261008_0140"
branch_labels = None
depends_on = None

_TABLE = "sol_reference_deidentification_confirmations"
_INSERT_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_deidentification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Reference deidentification history is immutable';
END; $$;
"""
_CLOSED_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_deidentification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Reference deidentification Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.execute(_INSERT_OWNER)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference confirmation Owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM plm.{_TABLE})")).scalar_one():
        raise RuntimeError("Reference confirmation history prevents Owner downgrade")
    op.execute(_CLOSED_OWNER)
