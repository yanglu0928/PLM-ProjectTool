"""Add PrototypePackage PATCH/SET_MEMBERS owner closure.

Revision ID: 20261008_0124
Revises: 20261008_0123
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0124"
down_revision = "20261008_0123"
branch_labels = None
depends_on = None

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_identity_scope_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='prt_packages' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'PrototypePackage initial state is invalid'; END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN
      RAISE EXCEPTION 'PrototypePackage history is immutable';
    END IF;
    IF NEW.prototype_package_id<>OLD.prototype_package_id
       OR NEW.project_id<>OLD.project_id OR NEW.created_by<>OLD.created_by
       OR NEW.created_at<>OLD.created_at OR NEW.updated_by IS NULL
       OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.package_state<>OLD.package_state OR OLD.package_state<>'ACTIVE' THEN
      RAISE EXCEPTION 'PrototypePackage mutation is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_package_memberships' THEN
    IF TG_OP='UPDATE' THEN
      RAISE EXCEPTION 'PrototypePackage membership history cannot be rewritten';
    ELSIF TG_OP='DELETE' THEN RETURN OLD;
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_prototypes' THEN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Prototype identity Owner is not installed'; END IF;
    IF NEW.prototype_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Prototype initial state is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME IN ('prt_scope_decisions','prt_scope_decision_requirement_refs') THEN
    RAISE EXCEPTION 'Prototype scope decision Owner is not installed';
  END IF;
  RAISE EXCEPTION 'Unknown Prototype identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_prototype_package_command_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_members uuid[];
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'PrototypePackage command result history is immutable'; END IF;
  SELECT COALESCE(array_agg(m.prototype_id ORDER BY m.prototype_id),ARRAY[]::uuid[])
    INTO actual_members FROM plm.prt_package_memberships m
   WHERE m.prototype_package_id=NEW.prototype_package_id
     AND m.project_id=NEW.project_id;
  IF NEW.member_refs<>actual_members OR array_position(NEW.member_refs,NULL) IS NOT NULL
     OR cardinality(NEW.member_refs)<>(SELECT count(DISTINCT x) FROM unnest(NEW.member_refs) x)
     OR NOT EXISTS (
       SELECT 1 FROM plm.prt_packages p
        WHERE p.prototype_package_id=NEW.prototype_package_id
          AND p.project_id=NEW.project_id AND p.name=NEW.name
          AND p.package_state=NEW.package_state AND p.lock_version=NEW.lock_version
          AND p.updated_by IS NOT NULL
     ) THEN RAISE EXCEPTION 'PrototypePackage command result does not match current root'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_package_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE package_id uuid; project uuid; current_lock bigint; actual_members uuid[];
BEGIN
  package_id:=CASE WHEN TG_TABLE_NAME='prt_packages' THEN NEW.prototype_package_id
                   ELSE COALESCE(NEW.prototype_package_id,OLD.prototype_package_id) END;
  project:=CASE WHEN TG_TABLE_NAME='prt_packages' THEN NEW.project_id
                ELSE COALESCE(NEW.project_id,OLD.project_id) END;
  SELECT p.lock_version,
         COALESCE(array_agg(m.prototype_id ORDER BY m.prototype_id)
                  FILTER (WHERE m.prototype_id IS NOT NULL),ARRAY[]::uuid[])
    INTO current_lock,actual_members FROM plm.prt_packages p
    LEFT JOIN plm.prt_package_memberships m
      ON m.prototype_package_id=p.prototype_package_id AND m.project_id=p.project_id
   WHERE p.prototype_package_id=package_id AND p.project_id=project
   GROUP BY p.lock_version;
  IF NOT EXISTS (
    SELECT 1 FROM plm.prt_package_command_results r
     WHERE r.prototype_package_id=package_id AND r.project_id=project
       AND r.lock_version=current_lock AND r.member_refs=actual_members
  ) THEN RAISE EXCEPTION 'PrototypePackage mutation has no immutable result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_package_command_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'PrototypePackage command result history cannot be truncated';
END; $$;
"""

_FOUNDATION = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_identity_scope_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME IN ('prt_scope_decisions','prt_scope_decision_requirement_refs') THEN
    RAISE EXCEPTION 'Prototype scope decision Owner is not installed'; END IF;
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Prototype identity Owner is not installed'; END IF;
  IF TG_TABLE_NAME='prt_packages' THEN
    IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'PrototypePackage initial state is invalid'; END IF;
  ELSIF TG_TABLE_NAME='prt_prototypes' THEN
    IF NEW.prototype_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Prototype initial state is invalid'; END IF;
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "prt_package_command_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("prototype_package_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("package_state", sa.Text(), nullable=False),
        sa.Column("member_refs", postgresql.ARRAY(ident), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["prototype_package_id","project_id"],
            ["plm.prt_packages.prototype_package_id","plm.prt_packages.project_id"],
            name="fk_prt_package_command_results__package", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("operation IN ('PATCH','SET_MEMBERS')",
                           name="ck_prt_package_command_results__operation"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                           name="ck_prt_package_command_results__name"),
        sa.CheckConstraint("package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                           name="ck_prt_package_command_results__state"),
        sa.CheckConstraint("lock_version>0", name="ck_prt_package_command_results__version"),
        schema="plm",
    )
    op.execute(_GUARDS)
    op.execute(sa.text(
        "CREATE TRIGGER trg_prt_package_command_results__immutable "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.prt_package_command_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_prototype_package_command_result()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_prt_package_command_results__no_truncate "
        "BEFORE TRUNCATE ON plm.prt_package_command_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_prototype_package_command_result_truncate()"
    ))
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_prt_packages__mutation_closure AFTER UPDATE "
        "ON plm.prt_packages DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_package_mutation_closure()"
    ))
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_prt_package_memberships__mutation_closure "
        "AFTER INSERT OR DELETE ON plm.prt_package_memberships DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.assert_prototype_package_mutation_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PrototypePackage mutation downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_package_command_results)"
    )).scalar_one():
        raise RuntimeError("PrototypePackage mutation history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_packages__mutation_closure ON plm.prt_packages")
    op.execute("DROP TRIGGER trg_prt_package_memberships__mutation_closure ON plm.prt_package_memberships")
    op.execute("DROP TRIGGER trg_prt_package_command_results__immutable ON plm.prt_package_command_results")
    op.execute("DROP TRIGGER trg_prt_package_command_results__no_truncate ON plm.prt_package_command_results")
    op.drop_table("prt_package_command_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_package_command_result()")
    op.execute("DROP FUNCTION plm.assert_prototype_package_mutation_closure()")
    op.execute("DROP FUNCTION plm.reject_prototype_package_command_result_truncate()")
    op.execute(_FOUNDATION)
