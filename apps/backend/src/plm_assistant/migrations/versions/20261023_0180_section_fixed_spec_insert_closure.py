"""Open only transaction-sealed fixed Spec refs on SectionVersion INSERT.

Revision ID: 20261023_0180
Revises: 20261023_0179
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261023_0180"
down_revision = "20261023_0179"
branch_labels = None
depends_on = None


_ROOT = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_binding_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND (
       (NEW.spec_binding_state='UNDECLARED'
        AND NEW.declared_spec_count=0 AND NEW.spec_not_required_reason IS NULL)
    OR (NEW.spec_binding_state='NONE_REQUIRED'
        AND NEW.declared_spec_count=0 AND NEW.spec_not_required_reason IS NOT NULL)
    OR (NEW.spec_binding_state='FIXED_REFS'
        AND NEW.declared_spec_count BETWEEN 1 AND 500
        AND NEW.spec_not_required_reason IS NULL)) THEN
    RETURN NEW;
  END IF;
  IF TG_OP='UPDATE'
     AND NEW.spec_binding_state IS NOT DISTINCT FROM OLD.spec_binding_state
     AND NEW.declared_spec_count IS NOT DISTINCT FROM OLD.declared_spec_count
     AND NEW.spec_not_required_reason IS NOT DISTINCT FROM OLD.spec_not_required_reason THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'SectionVersion Spec binding is immutable';
END; $$;
"""

_CHILD = r"""
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

_CLOSURE = r"""
CREATE OR REPLACE FUNCTION plm.assert_solution_section_version_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE requirement_count integer; requirement_min integer; requirement_max integer;
        evidence_count integer; evidence_min integer; evidence_max integer;
        spec_count integer; spec_min integer; spec_max integer;
BEGIN
  SELECT count(*),min(ordinal),max(ordinal)
    INTO requirement_count,requirement_min,requirement_max
    FROM plm.sol_section_requirement_refs
   WHERE solution_section_version_id=NEW.solution_section_version_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO evidence_count,evidence_min,evidence_max
    FROM plm.sol_section_evidence_refs
   WHERE solution_section_version_id=NEW.solution_section_version_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO spec_count,spec_min,spec_max
    FROM plm.sol_section_spec_refs
   WHERE solution_section_version_id=NEW.solution_section_version_id;
  IF requirement_count<>NEW.declared_requirement_count
     OR evidence_count<>NEW.declared_evidence_count
     OR spec_count<>NEW.declared_spec_count
     OR (requirement_count>0 AND (requirement_min<>1 OR requirement_max<>requirement_count))
     OR (evidence_count>0 AND (evidence_min<>1 OR evidence_max<>evidence_count))
     OR (spec_count>0 AND (spec_min<>1 OR spec_max<>spec_count))
     OR NOT EXISTS (
       SELECT 1 FROM plm.sol_section_version_create_results r
        WHERE r.solution_section_version_id=NEW.solution_section_version_id
          AND r.solution_section_id=NEW.solution_section_id
          AND r.project_id=NEW.project_id
          AND r.version_no=NEW.version_no
          AND r.content_fingerprint=NEW.content_fingerprint
     ) THEN RAISE EXCEPTION 'SolutionSectionVersion create set is incomplete'; END IF;
  RETURN NULL;
END; $$;
"""

_OLD_ROOT = r"""
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

_OLD_CHILD = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'SectionVersion SpecRef Owner is not installed'; END; $$;
"""

_OLD_CLOSURE = r"""
CREATE OR REPLACE FUNCTION plm.assert_solution_section_version_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE requirement_count integer; requirement_min integer; requirement_max integer;
        evidence_count integer; evidence_min integer; evidence_max integer;
BEGIN
  SELECT count(*),min(ordinal),max(ordinal)
    INTO requirement_count,requirement_min,requirement_max
    FROM plm.sol_section_requirement_refs
   WHERE solution_section_version_id=NEW.solution_section_version_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO evidence_count,evidence_min,evidence_max
    FROM plm.sol_section_evidence_refs
   WHERE solution_section_version_id=NEW.solution_section_version_id;
  IF requirement_count<>NEW.declared_requirement_count
     OR evidence_count<>NEW.declared_evidence_count
     OR (requirement_count>0 AND (requirement_min<>1 OR requirement_max<>requirement_count))
     OR (evidence_count>0 AND (evidence_min<>1 OR evidence_max<>evidence_count))
     OR NOT EXISTS (
       SELECT 1 FROM plm.sol_section_version_create_results r
        WHERE r.solution_section_version_id=NEW.solution_section_version_id
          AND r.solution_section_id=NEW.solution_section_id
          AND r.project_id=NEW.project_id
          AND r.version_no=NEW.version_no
          AND r.content_fingerprint=NEW.content_fingerprint
     ) THEN RAISE EXCEPTION 'SolutionSectionVersion create set is incomplete'; END IF;
  RETURN NULL;
END; $$;
"""


def _fixed_history() -> bool:
    return bool(op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_versions "
        "WHERE spec_binding_state='FIXED_REFS' OR declared_spec_count<>0) "
        "OR EXISTS (SELECT 1 FROM plm.sol_section_spec_refs)"
    )).scalar_one())


def upgrade() -> None:
    if not context.is_offline_mode() and _fixed_history():
        raise RuntimeError("unexpected Section SpecRef history before Owner")
    op.execute(_ROOT)
    op.execute(_CHILD)
    op.execute(_CLOSURE)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Section SpecRef Owner downgrade is disabled")
    if _fixed_history():
        raise RuntimeError("Section SpecRef history prevents downgrade")
    op.execute(_OLD_CLOSURE)
    op.execute(_OLD_CHILD)
    op.execute(_OLD_ROOT)
