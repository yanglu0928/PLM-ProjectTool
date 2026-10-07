"""Add Requirement Package mutation owner and immutable results.

Revision ID: 20261007_0113
Revises: 20261007_0112
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0113"
down_revision = "20261007_0112"
branch_labels = None
depends_on = None


_MUTATION_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='req_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'RequirementPackage initial state is invalid';
      END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN
      RAISE EXCEPTION 'RequirementPackage history is immutable';
    END IF;
    IF NEW.requirement_package_id<>OLD.requirement_package_id
       OR NEW.project_id<>OLD.project_id OR NEW.created_by<>OLD.created_by
       OR NEW.created_at<>OLD.created_at OR NEW.updated_by IS NULL
       OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR OLD.package_state='ARCHIVED'
       OR (OLD.package_state='ACTIVE' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED'))
       OR (OLD.package_state='RESTRICTED' AND NEW.package_state NOT IN ('ACTIVE','RESTRICTED','ARCHIVED')) THEN
      RAISE EXCEPTION 'RequirementPackage mutation is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF TG_OP<>'INSERT' THEN
      RAISE EXCEPTION 'Requirement identity Owner is not installed';
    END IF;
    IF NEW.requirement_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Requirement initial state is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='req_package_memberships' THEN
    IF TG_OP='UPDATE' THEN
      RAISE EXCEPTION 'RequirementPackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Requirement identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_requirement_package_command_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_members uuid[];
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'RequirementPackage command result history is immutable';
  END IF;
  SELECT COALESCE(array_agg(m.requirement_id ORDER BY m.requirement_id), ARRAY[]::uuid[])
    INTO actual_members FROM plm.req_package_memberships m
   WHERE m.requirement_package_id=NEW.requirement_package_id
     AND m.project_id=NEW.project_id;
  IF NEW.member_refs<>actual_members OR array_position(NEW.member_refs,NULL) IS NOT NULL
     OR cardinality(NEW.member_refs)<>(SELECT count(DISTINCT x) FROM unnest(NEW.member_refs) x)
     OR NOT EXISTS (
       SELECT 1 FROM plm.req_packages p
        WHERE p.requirement_package_id=NEW.requirement_package_id
          AND p.project_id=NEW.project_id AND p.name=NEW.name
          AND p.package_state=NEW.package_state AND p.lock_version=NEW.lock_version
          AND p.updated_by IS NOT NULL
     ) THEN
    RAISE EXCEPTION 'RequirementPackage command result does not match current root';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_package_command_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementPackage command result history cannot be truncated';
END; $$;
"""

_FOUNDATION_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Requirement identity Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='req_packages' THEN
    IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'RequirementPackage initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF NEW.requirement_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Requirement initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "req_package_command_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("requirement_package_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("package_state", sa.Text(), nullable=False),
        sa.Column("member_refs", postgresql.ARRAY(ident), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["requirement_package_id", "project_id"],
            ["plm.req_packages.requirement_package_id", "plm.req_packages.project_id"],
            name="fk_req_package_command_results__package", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("operation IN ('PATCH','ADD','REMOVE')",
                           name="ck_req_package_command_results__operation"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                           name="ck_req_package_command_results__name"),
        sa.CheckConstraint("package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                           name="ck_req_package_command_results__state"),
        sa.CheckConstraint("lock_version > 0",
                           name="ck_req_package_command_results__version"),
        schema="plm",
    )
    op.execute(_MUTATION_GUARDS)
    op.execute(sa.text(
        "CREATE TRIGGER trg_req_package_command_results__immutable "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.req_package_command_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_package_command_result()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_req_package_command_results__no_truncate "
        "BEFORE TRUNCATE ON plm.req_package_command_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_requirement_package_command_result_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Requirement Package mutation downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.req_package_command_results)"
    )).scalar_one():
        raise RuntimeError("Requirement Package mutation history prevents downgrade")
    op.execute("DROP TRIGGER trg_req_package_command_results__immutable ON plm.req_package_command_results")
    op.execute("DROP TRIGGER trg_req_package_command_results__no_truncate ON plm.req_package_command_results")
    op.drop_table("req_package_command_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_package_command_result()")
    op.execute("DROP FUNCTION plm.reject_requirement_package_command_result_truncate()")
    op.execute(_FOUNDATION_GUARD)
