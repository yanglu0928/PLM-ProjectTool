"""Permit only complete immutable SOL-06 draft inserts.

Revision ID: 20261012_0164
Revises: 20261012_0163
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261012_0164"
down_revision = "20261012_0163"
branch_labels = None
depends_on = None

_TABLES = (
    "sol_structured_specs", "sol_spec_payloads",
    "sol_spec_requirement_refs", "sol_spec_section_refs",
    "sol_spec_evidence_refs", "sol_spec_artifact_refs",
)

_OPEN = r"""
CREATE FUNCTION plm.structured_spec_created_in_current_transaction(
  version_id uuid, series_id uuid, project_ref uuid)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE creator_xmin xid;
BEGIN
  SELECT xmin INTO creator_xmin FROM plm.sol_structured_specs
   WHERE structured_solution_spec_id=version_id
     AND spec_series_id=series_id AND project_id=project_ref;
  RETURN creator_xmin IS NOT NULL AND
    creator_xmin::text::bigint = (txid_current() % 4294967296);
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_structured_solution_spec_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest_no integer; latest_id uuid; latest_project uuid; latest_type text;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec history is immutable';
  END IF;
  IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
     OR NEW.review_round_ref IS NOT NULL THEN
    RAISE EXCEPTION 'StructuredSolutionSpec initial state is invalid';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(
    'plm.sol_structured_specs:' || NEW.spec_series_id::text, 0));
  SELECT version_no,structured_solution_spec_id,project_id,spec_type
    INTO latest_no,latest_id,latest_project,latest_type
    FROM plm.sol_structured_specs WHERE spec_series_id=NEW.spec_series_id
   ORDER BY version_no DESC LIMIT 1;
  IF (latest_no IS NULL AND (
        NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
     OR (latest_no IS NOT NULL AND (
        NEW.version_no<>latest_no+1
        OR NEW.supersedes_version_ref IS DISTINCT FROM latest_id
        OR NEW.project_id<>latest_project OR NEW.spec_type<>latest_type)) THEN
    RAISE EXCEPTION 'StructuredSolutionSpec version chain is invalid';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_structured_spec_payload_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec payload history is immutable';
  END IF;
  IF NOT plm.structured_spec_created_in_current_transaction(
       NEW.structured_solution_spec_id,NEW.spec_series_id,NEW.project_id) THEN
    RAISE EXCEPTION 'StructuredSolutionSpec draft collection is sealed';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_structured_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec reference history is immutable';
  END IF;
  IF TG_TABLE_NAME='sol_spec_artifact_refs' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec OutputArtifact Owner is not installed';
  END IF;
  IF NOT plm.structured_spec_created_in_current_transaction(
       NEW.structured_solution_spec_id,NEW.spec_series_id,NEW.project_id) THEN
    RAISE EXCEPTION 'StructuredSolutionSpec draft collection is sealed';
  END IF;
  RETURN NEW;
END; $$;

CREATE FUNCTION plm.assert_structured_spec_insert_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE payload_count integer; requirement_count integer; requirement_min integer;
        requirement_max integer; section_count integer; section_min integer;
        section_max integer; evidence_count integer; evidence_min integer;
        evidence_max integer; artifact_count integer;
BEGIN
  SELECT count(*) INTO payload_count FROM plm.sol_spec_payloads
   WHERE structured_solution_spec_id=NEW.structured_solution_spec_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO requirement_count,requirement_min,requirement_max
    FROM plm.sol_spec_requirement_refs
   WHERE structured_solution_spec_id=NEW.structured_solution_spec_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO section_count,section_min,section_max
    FROM plm.sol_spec_section_refs
   WHERE structured_solution_spec_id=NEW.structured_solution_spec_id;
  SELECT count(*),min(ordinal),max(ordinal)
    INTO evidence_count,evidence_min,evidence_max
    FROM plm.sol_spec_evidence_refs
   WHERE structured_solution_spec_id=NEW.structured_solution_spec_id;
  SELECT count(*) INTO artifact_count FROM plm.sol_spec_artifact_refs
   WHERE structured_solution_spec_id=NEW.structured_solution_spec_id;
  IF payload_count<>1 OR requirement_count<1 OR section_count<1
     OR requirement_min<>1 OR requirement_max<>requirement_count
     OR section_min<>1 OR section_max<>section_count
     OR (evidence_count>0 AND (evidence_min<>1 OR evidence_max<>evidence_count))
     OR artifact_count<>0 THEN
    RAISE EXCEPTION 'StructuredSolutionSpec draft collection is incomplete';
  END IF;
  RETURN NULL;
END; $$;
"""

_CLOSED = r"""
CREATE OR REPLACE FUNCTION plm.guard_structured_solution_spec_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'StructuredSolutionSpec write Owner is not installed'; END; $$;
CREATE OR REPLACE FUNCTION plm.guard_structured_spec_payload_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'StructuredSolutionSpec payload Owner is not installed'; END; $$;
CREATE OR REPLACE FUNCTION plm.guard_structured_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'StructuredSolutionSpec reference Owner is not installed'; END; $$;
"""


def _has_history() -> bool:
    bind = op.get_bind()
    return any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _TABLES)


def upgrade() -> None:
    if not context.is_offline_mode() and _has_history():
        raise RuntimeError("pre-existing StructuredSolutionSpec requires audited Owner migration")
    op.execute(_OPEN)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_specs__insert_closure "
        "AFTER INSERT ON plm.sol_structured_specs DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_structured_spec_insert_closure()"))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline StructuredSolutionSpec guard downgrade is disabled")
    if _has_history():
        raise RuntimeError("StructuredSolutionSpec history prevents guard downgrade")
    op.execute("DROP TRIGGER trg_sol_specs__insert_closure ON plm.sol_structured_specs")
    op.execute("DROP FUNCTION plm.assert_structured_spec_insert_closure()")
    op.execute(_CLOSED)
    op.execute("DROP FUNCTION plm.structured_spec_created_in_current_transaction(uuid,uuid,uuid)")
