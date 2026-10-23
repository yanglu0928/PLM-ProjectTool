"""Add nullable but write-closed Section Spec fit rationale.

Revision ID: 20261023_0181
Revises: 20261023_0180
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261023_0181"
down_revision = "20261023_0180"
branch_labels = None
depends_on = None


_CLOSED_WITH_FIT = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_count integer; creator_xmin xid;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'SectionVersion SpecRef history is immutable';
  END IF;
  IF NEW.fit_rationale IS NOT NULL THEN
    RAISE EXCEPTION 'SectionVersion Spec fit Owner is not installed';
  END IF;
  SELECT v.declared_spec_count,v.xmin INTO expected_count,creator_xmin
    FROM plm.sol_section_versions v
   WHERE v.solution_section_version_id=NEW.solution_section_version_id
     AND v.solution_section_id=NEW.solution_section_id
     AND v.project_id=NEW.project_id
     AND v.spec_binding_state='FIXED_REFS';
  IF NOT FOUND OR NEW.ordinal>expected_count
     OR creator_xmin::text::bigint <> (txid_current() % 4294967296) THEN
    RAISE EXCEPTION 'SectionVersion SpecRef collection is sealed';
  END IF;
  RETURN NEW;
END; $$;
"""

_PREVIOUS = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_count integer; creator_xmin xid;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'SectionVersion SpecRef history is immutable';
  END IF;
  SELECT v.declared_spec_count,v.xmin INTO expected_count,creator_xmin
    FROM plm.sol_section_versions v
   WHERE v.solution_section_version_id=NEW.solution_section_version_id
     AND v.solution_section_id=NEW.solution_section_id
     AND v.project_id=NEW.project_id
     AND v.spec_binding_state='FIXED_REFS';
  IF NOT FOUND OR NEW.ordinal>expected_count
     OR creator_xmin::text::bigint <> (txid_current() % 4294967296) THEN
    RAISE EXCEPTION 'SectionVersion SpecRef collection is sealed';
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    op.add_column("sol_section_spec_refs", sa.Column(
        "fit_rationale", sa.Text()), schema="plm")
    op.create_check_constraint(
        "ck_sol_section_specs__fit_rationale", "sol_section_spec_refs",
        "fit_rationale IS NULL OR (char_length(fit_rationale) BETWEEN 1 AND 1000 "
        "AND fit_rationale=btrim(fit_rationale))", schema="plm")
    op.execute(_CLOSED_WITH_FIT)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Section Spec fit downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_spec_refs "
        "WHERE fit_rationale IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Section Spec fit history prevents downgrade")
    op.execute(_PREVIOUS)
    op.drop_constraint("ck_sol_section_specs__fit_rationale",
                       "sol_section_spec_refs", schema="plm", type_="check")
    op.drop_column("sol_section_spec_refs", "fit_rationale", schema="plm")
