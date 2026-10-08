"""Open INSERT-only ReferenceSolution identity/version/source Owner.

Revision ID: 20261008_0144
Revises: 20261008_0143
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261008_0144"
down_revision = "20261008_0143"
branch_labels = None
depends_on = None

_TABLES = ("sol_reference_solutions", "sol_reference_versions",
           "sol_reference_document_refs", "sol_reference_evidence_refs")
_INSERT_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ReferenceSolution history is immutable';
END; $$;
"""
_CLOSED_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ReferenceSolution Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.execute(_INSERT_OWNER)


def downgrade() -> None:
    if context.is_offline_mode():
        op.execute(sa.text(
            "DO $reference_guard$ BEGIN "
            "IF EXISTS (SELECT 1 FROM plm.sol_reference_solutions) OR "
            "EXISTS (SELECT 1 FROM plm.sol_reference_versions) OR "
            "EXISTS (SELECT 1 FROM plm.sol_reference_document_refs) OR "
            "EXISTS (SELECT 1 FROM plm.sol_reference_evidence_refs) THEN "
            "RAISE EXCEPTION 'ReferenceSolution history prevents Owner downgrade'; "
            "END IF; END $reference_guard$;"))
    else:
        for table in _TABLES:
            if op.get_bind().execute(sa.text(
                    f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
                raise RuntimeError("ReferenceSolution history prevents Owner downgrade")
    op.execute(_CLOSED_OWNER)
