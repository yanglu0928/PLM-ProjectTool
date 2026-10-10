"""Open INSERT-only OutlineVersion collection with deferred closure.

Revision ID: 20261009_0156
Revises: 20261009_0155
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0156"
down_revision = "20261009_0155"
branch_labels = None
depends_on = None


_OPEN = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_outline_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root_state text; latest_no integer; latest_id uuid; expected_count integer;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'SolutionOutlineVersion history is immutable';
  END IF;
  IF TG_TABLE_NAME='sol_outline_versions' THEN
    SELECT outline_state INTO root_state FROM plm.sol_outlines
     WHERE solution_outline_id=NEW.solution_outline_id
       AND project_id=NEW.project_id FOR UPDATE;
    IF NOT FOUND OR root_state<>'ACTIVE' OR NEW.version_state<>'DRAFT'
       OR NEW.review_ref IS NOT NULL OR NEW.review_round_ref IS NOT NULL
       OR NEW.declared_section_count<1
       OR NEW.declared_reference_count>500
       OR jsonb_array_length(NEW.missing_declarations)>100
       OR jsonb_array_length(NEW.conflict_declarations)>100
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.missing_declarations) AS item
                   WHERE jsonb_typeof(item)<>'object')
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.conflict_declarations) AS item
                   WHERE jsonb_typeof(item)<>'object')
       OR (NEW.declared_requirement_count=0 AND NEW.declared_reference_count=0
           AND jsonb_array_length(NEW.missing_declarations)=0) THEN
      RAISE EXCEPTION 'SolutionOutlineVersion initial state is invalid';
    END IF;
    SELECT version_no,solution_outline_version_id INTO latest_no,latest_id
      FROM plm.sol_outline_versions
     WHERE solution_outline_id=NEW.solution_outline_id
       AND project_id=NEW.project_id ORDER BY version_no DESC LIMIT 1;
    IF (latest_no IS NULL AND
        (NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
       OR (latest_no IS NOT NULL AND
           (NEW.version_no<>latest_no+1 OR
            NEW.supersedes_version_ref IS DISTINCT FROM latest_id)) THEN
      RAISE EXCEPTION 'SolutionOutlineVersion chain is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_outline_sections' THEN
    SELECT declared_section_count INTO expected_count
      FROM plm.sol_outline_versions WHERE solution_outline_version_id=NEW.solution_outline_version_id
        AND solution_outline_id=NEW.solution_outline_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_count THEN
      RAISE EXCEPTION 'SolutionOutlineVersion SectionRef is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_outline_requirement_refs' THEN
    SELECT declared_requirement_count INTO expected_count
      FROM plm.sol_outline_versions WHERE solution_outline_version_id=NEW.solution_outline_version_id
        AND solution_outline_id=NEW.solution_outline_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_count THEN
      RAISE EXCEPTION 'SolutionOutlineVersion RequirementRef is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_outline_reference_refs' THEN
    SELECT declared_reference_count INTO expected_count
      FROM plm.sol_outline_versions WHERE solution_outline_version_id=NEW.solution_outline_version_id
        AND solution_outline_id=NEW.solution_outline_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_count THEN
      RAISE EXCEPTION 'SolutionOutlineVersion ReferenceRef is invalid'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown SolutionOutlineVersion table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_solution_outline_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'SolutionOutlineVersion create result is immutable'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM plm.sol_outline_versions v
     WHERE v.solution_outline_version_id=NEW.solution_outline_version_id
       AND v.solution_outline_id=NEW.solution_outline_id
       AND v.project_id=NEW.project_id AND v.version_no=NEW.version_no
       AND v.version_state='DRAFT' AND v.review_ref IS NULL
       AND v.review_round_ref IS NULL
       AND v.content_fingerprint=NEW.content_fingerprint
       AND v.missing_declarations=NEW.missing_declarations
       AND v.conflict_declarations=NEW.conflict_declarations
       AND v.declared_section_count=NEW.declared_section_count
       AND v.declared_requirement_count=NEW.declared_requirement_count
       AND v.declared_reference_count=NEW.declared_reference_count
       AND v.supersedes_version_ref IS NOT DISTINCT FROM NEW.supersedes_version_ref
       AND v.created_by=NEW.created_by AND v.created_at=NEW.created_at
  ) THEN RAISE EXCEPTION 'SolutionOutlineVersion result does not match version'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_solution_outline_version_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE section_count integer; section_min integer; section_max integer;
        requirement_count integer; requirement_min integer; requirement_max integer;
        reference_count integer; reference_min integer; reference_max integer;
BEGIN
  SELECT count(*),min(ordinal),max(ordinal)
    INTO section_count,section_min,section_max
    FROM plm.sol_outline_sections WHERE solution_outline_version_id=NEW.solution_outline_version_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO requirement_count,requirement_min,requirement_max
    FROM plm.sol_outline_requirement_refs WHERE solution_outline_version_id=NEW.solution_outline_version_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO reference_count,reference_min,reference_max
    FROM plm.sol_outline_reference_refs WHERE solution_outline_version_id=NEW.solution_outline_version_id;
  IF section_count<>NEW.declared_section_count
     OR requirement_count<>NEW.declared_requirement_count
     OR reference_count<>NEW.declared_reference_count
     OR (section_count>0 AND (section_min<>1 OR section_max<>section_count))
     OR (requirement_count>0 AND (requirement_min<>1 OR requirement_max<>requirement_count))
     OR (reference_count>0 AND (reference_min<>1 OR reference_max<>reference_count))
     OR NOT EXISTS (
       SELECT 1 FROM plm.sol_outline_version_create_results r
        WHERE r.solution_outline_version_id=NEW.solution_outline_version_id
          AND r.solution_outline_id=NEW.solution_outline_id
          AND r.project_id=NEW.project_id
          AND r.content_fingerprint=NEW.content_fingerprint
          AND r.version_no=NEW.version_no
     ) THEN RAISE EXCEPTION 'SolutionOutlineVersion create set is incomplete'; END IF;
  RETURN NULL;
END; $$;
"""


_CLOSED = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_outline_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'SolutionOutlineVersion Owner is not installed'; END; $$;
CREATE OR REPLACE FUNCTION plm.guard_solution_outline_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'SolutionOutlineVersion create result Owner is not installed'; END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode() and op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outline_versions) OR "
        "EXISTS (SELECT 1 FROM plm.sol_outline_version_create_results)"
    )).scalar_one():
        raise RuntimeError("pre-existing OutlineVersion requires audited Owner migration")
    op.execute(_OPEN)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_outline_versions__create_closure "
        "AFTER INSERT ON plm.sol_outline_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_solution_outline_version_create_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline OutlineVersion Owner guard downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outline_versions) OR "
        "EXISTS (SELECT 1 FROM plm.sol_outline_version_create_results)"
    )).scalar_one():
        raise RuntimeError("OutlineVersion history prevents Owner guard downgrade")
    op.execute("DROP TRIGGER trg_sol_outline_versions__create_closure "
               "ON plm.sol_outline_versions")
    op.execute("DROP FUNCTION plm.assert_solution_outline_version_create_closure()")
    op.execute(_CLOSED)
