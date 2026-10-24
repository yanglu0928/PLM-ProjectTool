"""Open only explicit NONE_REQUIRED Section Spec declarations; refs stay closed.

Revision ID: 20261023_0179
Revises: 20261023_0178
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261023_0179"
down_revision = "20261023_0178"
branch_labels = None
depends_on = None


_FUNCTION = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_binding_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND NEW.declared_spec_count=0
     AND ((NEW.spec_binding_state='UNDECLARED'
           AND NEW.spec_not_required_reason IS NULL)
          OR (NEW.spec_binding_state='NONE_REQUIRED'
              AND NEW.spec_not_required_reason IS NOT NULL)) THEN
    RETURN NEW;
  END IF;
  IF TG_OP='UPDATE'
     AND NEW.spec_binding_state IS NOT DISTINCT FROM OLD.spec_binding_state
     AND NEW.declared_spec_count IS NOT DISTINCT FROM OLD.declared_spec_count
     AND NEW.spec_not_required_reason IS NOT DISTINCT FROM OLD.spec_not_required_reason THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'SectionVersion Spec binding Owner is not installed';
END; $$;
"""

_CLOSED_FUNCTION = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_binding_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND NEW.spec_binding_state='UNDECLARED'
     AND NEW.declared_spec_count=0 AND NEW.spec_not_required_reason IS NULL THEN
    RETURN NEW;
  END IF;
  IF TG_OP='UPDATE'
     AND NEW.spec_binding_state IS NOT DISTINCT FROM OLD.spec_binding_state
     AND NEW.declared_spec_count IS NOT DISTINCT FROM OLD.declared_spec_count
     AND NEW.spec_not_required_reason IS NOT DISTINCT FROM OLD.spec_not_required_reason THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'SectionVersion Spec binding Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode() and op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_versions "
        "WHERE spec_binding_state<>'UNDECLARED') "
        "OR EXISTS (SELECT 1 FROM plm.sol_section_spec_refs)"
    )).scalar_one():
        raise RuntimeError("unexpected SectionVersion Spec binding history before Owner")
    op.execute(_FUNCTION)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SectionVersion Spec Owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_versions "
        "WHERE spec_binding_state<>'UNDECLARED') "
        "OR EXISTS (SELECT 1 FROM plm.sol_section_spec_refs)"
    )).scalar_one():
        raise RuntimeError("SectionVersion Spec binding history prevents downgrade")
    op.execute(_CLOSED_FUNCTION)
