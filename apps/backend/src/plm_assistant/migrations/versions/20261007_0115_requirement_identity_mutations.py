"""Open Requirement identity mutation owner and immutable results.

Revision ID: 20261007_0115
Revises: 20261007_0114
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0115"
down_revision = "20261007_0114"
branch_labels = None
depends_on = None

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='req_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'RequirementPackage initial state is invalid';
      END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'RequirementPackage history is immutable'; END IF;
    IF NEW.requirement_package_id<>OLD.requirement_package_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR OLD.package_state='ARCHIVED'
       OR (OLD.package_state='ACTIVE' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED'))
       OR (OLD.package_state='RESTRICTED' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED')) THEN
      RAISE EXCEPTION 'RequirementPackage mutation is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.requirement_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Requirement initial state is invalid';
      END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'Requirement identity history is immutable'; END IF;
    IF NEW.requirement_id<>OLD.requirement_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.requirement_code_normalized<>upper(NEW.requirement_code)
       OR NOT (
         (OLD.requirement_state='ACTIVE' AND NEW.requirement_state='ACTIVE'
          AND NEW.requirement_code<>OLD.requirement_code)
         OR (OLD.requirement_state='ACTIVE' AND NEW.requirement_state IN ('DEFERRED','REJECTED')
             AND NEW.requirement_code=OLD.requirement_code)
         OR (OLD.requirement_state<>'ARCHIVED' AND NEW.requirement_state='ARCHIVED'
             AND NEW.requirement_code=OLD.requirement_code)
       ) THEN
      RAISE EXCEPTION 'Requirement identity mutation is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='req_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'RequirementPackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Requirement identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_state_decision_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Requirement state decision history is immutable'; END IF;
  IF TG_TABLE_NAME='req_requirement_state_decisions' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.req_requirements r
       WHERE r.requirement_id=NEW.requirement_id AND r.project_id=NEW.project_id
         AND r.lock_version=NEW.after_version AND r.updated_by=NEW.decided_by
         AND ((NEW.decision_type='DEFER' AND r.requirement_state='DEFERRED')
           OR (NEW.decision_type='REJECT' AND r.requirement_state='REJECTED'))
    ) THEN RAISE EXCEPTION 'Requirement decision does not match current root'; END IF;
  ELSIF TG_TABLE_NAME='req_requirement_decision_evidence_refs' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.evd_evidence_records e
       WHERE e.evidence_id=NEW.evidence_id AND e.scope='PROJECT'
         AND e.project_id=NEW.project_id AND e.eligibility_state='ELIGIBLE'
    ) THEN RAISE EXCEPTION 'Requirement decision Evidence is not eligible'; END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_command_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_evidence uuid[];
BEGIN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Requirement command result history is immutable'; END IF;
  IF array_position(NEW.evidence_refs,NULL) IS NOT NULL
     OR cardinality(NEW.evidence_refs)<>(SELECT count(DISTINCT x) FROM unnest(NEW.evidence_refs) x)
     OR NEW.evidence_refs<>(SELECT COALESCE(array_agg(x ORDER BY x),ARRAY[]::uuid[])
                              FROM unnest(NEW.evidence_refs) x) THEN
    RAISE EXCEPTION 'Requirement command result Evidence is not canonical';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM plm.req_requirements r
     WHERE r.requirement_id=NEW.requirement_id AND r.project_id=NEW.project_id
       AND r.requirement_code=NEW.requirement_code
       AND r.requirement_state=NEW.requirement_state AND r.lock_version=NEW.lock_version
  ) THEN RAISE EXCEPTION 'Requirement command result does not match current root'; END IF;
  IF NEW.operation IN ('DEFER','REJECT') THEN
    SELECT COALESCE(array_agg(e.evidence_id ORDER BY e.evidence_id),ARRAY[]::uuid[])
      INTO actual_evidence FROM plm.req_requirement_decision_evidence_refs e
     WHERE e.decision_id=NEW.decision_id AND e.requirement_id=NEW.requirement_id
       AND e.project_id=NEW.project_id;
    IF actual_evidence<>NEW.evidence_refs OR NOT EXISTS (
      SELECT 1 FROM plm.req_requirement_state_decisions d
       WHERE d.decision_id=NEW.decision_id AND d.requirement_id=NEW.requirement_id
         AND d.project_id=NEW.project_id AND d.decision_type=NEW.operation
         AND d.reason=NEW.reason AND d.impact=NEW.impact
         AND d.after_version=NEW.lock_version
    ) THEN RAISE EXCEPTION 'Requirement command result does not match decision'; END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_requirement_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.req_requirement_command_results x
     WHERE x.requirement_id=NEW.requirement_id AND x.project_id=NEW.project_id
       AND x.requirement_code=NEW.requirement_code
       AND x.requirement_state=NEW.requirement_state AND x.lock_version=NEW.lock_version
  ) THEN RAISE EXCEPTION 'Requirement mutation has no immutable result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_requirement_decision_evidence()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM plm.req_requirement_decision_evidence_refs e
                  WHERE e.decision_id=NEW.decision_id) THEN
    RAISE EXCEPTION 'Requirement decision requires Evidence';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_command_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Requirement command result history cannot be truncated';
END; $$;
"""

_DOWN_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_state_decision_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Requirement state decision Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='req_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'RequirementPackage initial state is invalid'; END IF; RETURN NEW;
    ELSIF TG_OP='DELETE' THEN RAISE EXCEPTION 'RequirementPackage history is immutable'; END IF;
    IF NEW.requirement_package_id<>OLD.requirement_package_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1 OR OLD.package_state='ARCHIVED' THEN
      RAISE EXCEPTION 'RequirementPackage mutation is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Requirement identity Owner is not installed'; END IF;
    IF NEW.requirement_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Requirement initial state is invalid'; END IF; RETURN NEW;
  ELSIF TG_TABLE_NAME='req_package_memberships' THEN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'RequirementPackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
  END IF;
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "req_requirement_command_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("requirement_code", sa.Text(), nullable=False),
        sa.Column("requirement_state", sa.Text(), nullable=False),
        sa.Column("decision_id", ident), sa.Column("reason", sa.Text()),
        sa.Column("impact", sa.Text()),
        sa.Column("evidence_refs", postgresql.ARRAY(ident), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_command_results__requirement", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["decision_id", "requirement_id", "project_id"],
            ["plm.req_requirement_state_decisions.decision_id",
             "plm.req_requirement_state_decisions.requirement_id",
             "plm.req_requirement_state_decisions.project_id"],
            name="fk_req_command_results__decision", ondelete="NO ACTION"),
        sa.CheckConstraint("operation IN ('PATCH','DEFER','REJECT','ARCHIVE')",
                           name="ck_req_command_results__operation"),
        sa.CheckConstraint("requirement_code ~ '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'",
                           name="ck_req_command_results__code"),
        sa.CheckConstraint("requirement_state IN ('ACTIVE','DEFERRED','REJECTED','ARCHIVED')",
                           name="ck_req_command_results__state"),
        sa.CheckConstraint("(operation='PATCH' AND requirement_state='ACTIVE' AND decision_id IS NULL AND reason IS NULL AND impact IS NULL AND cardinality(evidence_refs)=0) OR (operation='ARCHIVE' AND requirement_state='ARCHIVED' AND decision_id IS NULL AND reason IS NULL AND impact IS NULL AND cardinality(evidence_refs)=0) OR (operation='DEFER' AND requirement_state='DEFERRED' AND decision_id IS NOT NULL AND reason IS NOT NULL AND impact IS NOT NULL AND cardinality(evidence_refs)>0) OR (operation='REJECT' AND requirement_state='REJECTED' AND decision_id IS NOT NULL AND reason IS NOT NULL AND impact IS NOT NULL AND cardinality(evidence_refs)>0)",
                           name="ck_req_command_results__shape"),
        sa.CheckConstraint("lock_version>0", name="ck_req_command_results__version"),
        schema="plm",
    )
    op.execute(_GUARDS)
    op.execute("CREATE TRIGGER trg_req_requirement_command_results__immutable BEFORE INSERT OR UPDATE OR DELETE ON plm.req_requirement_command_results FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_command_result()")
    op.execute("CREATE TRIGGER trg_req_requirement_command_results__no_truncate BEFORE TRUNCATE ON plm.req_requirement_command_results FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_requirement_command_result_truncate()")
    op.execute("CREATE CONSTRAINT TRIGGER trg_req_requirements__mutation_closure AFTER UPDATE ON plm.req_requirements DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.enforce_requirement_mutation_closure()")
    op.execute("CREATE CONSTRAINT TRIGGER trg_req_state_decisions__evidence_closure AFTER INSERT ON plm.req_requirement_state_decisions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.enforce_requirement_decision_evidence()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Requirement mutation downgrade is disabled")
    bind = op.get_bind()
    for table in ("req_requirement_command_results", "req_requirement_state_decisions",
                  "req_requirement_decision_evidence_refs"):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Requirement mutation history prevents downgrade")
    op.execute("DROP TRIGGER trg_req_requirements__mutation_closure ON plm.req_requirements")
    op.execute("DROP TRIGGER trg_req_state_decisions__evidence_closure ON plm.req_requirement_state_decisions")
    op.execute("DROP TRIGGER trg_req_requirement_command_results__immutable ON plm.req_requirement_command_results")
    op.execute("DROP TRIGGER trg_req_requirement_command_results__no_truncate ON plm.req_requirement_command_results")
    op.drop_table("req_requirement_command_results", schema="plm")
    for function in ("guard_requirement_command_result", "enforce_requirement_mutation_closure",
                     "enforce_requirement_decision_evidence",
                     "reject_requirement_command_result_truncate"):
        op.execute(sa.text(f"DROP FUNCTION plm.{function}()"))
    op.execute(_DOWN_GUARDS)
