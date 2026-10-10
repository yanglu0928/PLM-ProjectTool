"""Open INSERT-only Document-backed SectionVersion collection with closure.

Revision ID: 20261009_0160
Revises: 20261009_0159
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0160"
down_revision = "20261009_0159"
branch_labels = None
depends_on = None


_HISTORY = (
    "sol_section_versions", "sol_section_requirement_refs",
    "sol_section_evidence_refs", "sol_section_version_create_results",
)

_OPEN = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_section_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE outline_id uuid; outline_state_value text; section_state_value text;
        latest_no integer; latest_id uuid; expected_count integer;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'SolutionSectionVersion history is immutable';
  END IF;
  IF TG_TABLE_NAME='sol_section_versions' THEN
    SELECT solution_outline_id INTO outline_id FROM plm.sol_sections
     WHERE solution_section_id=NEW.solution_section_id AND project_id=NEW.project_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'SolutionSectionVersion parent is invalid'; END IF;
    SELECT outline_state INTO outline_state_value FROM plm.sol_outlines
     WHERE solution_outline_id=outline_id AND project_id=NEW.project_id FOR UPDATE;
    SELECT section_state INTO section_state_value FROM plm.sol_sections
     WHERE solution_section_id=NEW.solution_section_id AND project_id=NEW.project_id
       AND solution_outline_id=outline_id FOR UPDATE;
    IF outline_state_value IS DISTINCT FROM 'ACTIVE'
       OR section_state_value IS DISTINCT FROM 'ACTIVE'
       OR NEW.version_state<>'DRAFT'
       OR NEW.review_ref IS NOT NULL OR NEW.review_round_ref IS NOT NULL
       OR NEW.content_document_version_ref IS NULL
       OR NEW.content_artifact_ref IS NOT NULL
       OR jsonb_array_length(NEW.assumptions)>100
       OR jsonb_array_length(NEW.exclusions)>100
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.assumptions) item
                   WHERE jsonb_typeof(item)<>'object')
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.exclusions) item
                   WHERE jsonb_typeof(item)<>'object') THEN
      RAISE EXCEPTION 'SolutionSectionVersion initial state is invalid';
    END IF;
    SELECT version_no,solution_section_version_id INTO latest_no,latest_id
      FROM plm.sol_section_versions
     WHERE solution_section_id=NEW.solution_section_id AND project_id=NEW.project_id
     ORDER BY version_no DESC LIMIT 1;
    IF (latest_no IS NULL AND
        (NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
       OR (latest_no IS NOT NULL AND
           (NEW.version_no<>latest_no+1 OR
            NEW.supersedes_version_ref IS DISTINCT FROM latest_id)) THEN
      RAISE EXCEPTION 'SolutionSectionVersion chain is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_section_requirement_refs' THEN
    SELECT declared_requirement_count INTO expected_count
      FROM plm.sol_section_versions
     WHERE solution_section_version_id=NEW.solution_section_version_id
       AND solution_section_id=NEW.solution_section_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_count THEN
      RAISE EXCEPTION 'SolutionSectionVersion RequirementRef is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_section_evidence_refs' THEN
    SELECT declared_evidence_count INTO expected_count
      FROM plm.sol_section_versions
     WHERE solution_section_version_id=NEW.solution_section_version_id
       AND solution_section_id=NEW.solution_section_id AND project_id=NEW.project_id;
    IF NOT FOUND OR NEW.ordinal>expected_count THEN
      RAISE EXCEPTION 'SolutionSectionVersion EvidenceRef is invalid'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown SolutionSectionVersion table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_solution_section_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'SolutionSectionVersion create result is immutable'; END IF;
  IF NEW.content_document_version_ref IS NULL OR NEW.content_artifact_ref IS NOT NULL
     OR NOT EXISTS (
       SELECT 1 FROM plm.sol_section_versions v
        WHERE v.solution_section_version_id=NEW.solution_section_version_id
          AND v.solution_section_id=NEW.solution_section_id
          AND v.project_id=NEW.project_id
          AND v.version_no=NEW.version_no
          AND v.version_state='DRAFT'
          AND v.review_ref IS NULL AND v.review_round_ref IS NULL
          AND v.title=NEW.title
          AND v.content_document_version_ref=NEW.content_document_version_ref
          AND v.content_artifact_ref IS NULL
          AND v.content_fingerprint=NEW.content_fingerprint
          AND v.assumptions=NEW.assumptions AND v.exclusions=NEW.exclusions
          AND v.declared_requirement_count=NEW.declared_requirement_count
          AND v.declared_evidence_count=NEW.declared_evidence_count
          AND v.supersedes_version_ref IS NOT DISTINCT FROM NEW.supersedes_version_ref
          AND v.created_by=NEW.created_by AND v.created_at=NEW.created_at
     ) THEN
    RAISE EXCEPTION 'SolutionSectionVersion result does not match version';
  END IF;
  RETURN NEW;
END; $$;

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


_CLOSED = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_section_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'SolutionSectionVersion Owner is not installed'; END; $$;
CREATE OR REPLACE FUNCTION plm.guard_solution_section_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'SolutionSectionVersion create result Owner is not installed'; END; $$;
"""


def _has_history() -> bool:
    return op.get_bind().execute(sa.text("SELECT " + " OR ".join(
        f"EXISTS (SELECT 1 FROM plm.{table})" for table in _HISTORY
    ))).scalar_one()


def upgrade() -> None:
    if not context.is_offline_mode() and _has_history():
        raise RuntimeError("pre-existing SectionVersion requires audited Owner migration")
    op.execute(_OPEN)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_section_versions__create_closure "
        "AFTER INSERT ON plm.sol_section_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_solution_section_version_create_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SectionVersion Owner guard downgrade is disabled")
    if _has_history():
        raise RuntimeError("SectionVersion history prevents Owner guard downgrade")
    op.execute("DROP TRIGGER trg_sol_section_versions__create_closure "
               "ON plm.sol_section_versions")
    op.execute("DROP FUNCTION plm.assert_solution_section_version_create_closure()")
    op.execute(_CLOSED)
