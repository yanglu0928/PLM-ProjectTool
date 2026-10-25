"""Open Prototype PATCH/ARCHIVE owner and immutable results.

Revision ID: 20261008_0125
Revises: 20261008_0124
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0125"
down_revision = "20261008_0124"
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
    IF TG_OP='INSERT' THEN
      IF NEW.prototype_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
        RAISE EXCEPTION 'Prototype initial state is invalid'; END IF;
      RETURN NEW;
    ELSIF TG_OP='DELETE' THEN
      RAISE EXCEPTION 'Prototype identity history is immutable';
    END IF;
    IF NEW.prototype_id<>OLD.prototype_id OR NEW.project_id<>OLD.project_id
       OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.updated_by IS NULL OR NEW.updated_at<>statement_timestamp()
       OR NEW.lock_version<>OLD.lock_version+1
       OR NOT (
         (OLD.prototype_state='ACTIVE' AND NEW.prototype_state='ACTIVE'
          AND NEW.name<>OLD.name)
         OR (OLD.prototype_state<>'ARCHIVED' AND NEW.prototype_state='ARCHIVED'
             AND NEW.name=OLD.name)
       ) THEN RAISE EXCEPTION 'Prototype identity mutation is invalid'; END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME IN ('prt_scope_decisions','prt_scope_decision_requirement_refs') THEN
    RAISE EXCEPTION 'Prototype scope decision Owner is not installed';
  END IF;
  RAISE EXCEPTION 'Unknown Prototype identity table';
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_prototype_command_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Prototype command result history is immutable'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM plm.prt_prototypes p
     WHERE p.prototype_id=NEW.prototype_id AND p.project_id=NEW.project_id
       AND p.name=NEW.name AND p.prototype_state=NEW.prototype_state
       AND p.current_approved_version_ref IS NOT DISTINCT FROM
           NEW.current_approved_version_ref
       AND p.lock_version=NEW.lock_version AND p.updated_by IS NOT NULL
  ) THEN RAISE EXCEPTION 'Prototype command result does not match current root'; END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_mutation_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.prt_prototype_command_results r
     WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
       AND r.name=NEW.name AND r.prototype_state=NEW.prototype_state
       AND r.current_approved_version_ref IS NOT DISTINCT FROM
           NEW.current_approved_version_ref
       AND r.lock_version=NEW.lock_version
  ) THEN RAISE EXCEPTION 'Prototype mutation has no immutable result'; END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_command_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Prototype command result history cannot be truncated';
END; $$;
"""

_DOWN_GUARD = r"""
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
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "prt_prototype_command_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("prototype_state", sa.Text(), nullable=False),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_prototype_command_results__prototype", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("operation IN ('PATCH','ARCHIVE')",
                           name="ck_prt_prototype_command_results__operation"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                           name="ck_prt_prototype_command_results__name"),
        sa.CheckConstraint("prototype_state IN ('ACTIVE','ARCHIVED')",
                           name="ck_prt_prototype_command_results__state"),
        sa.CheckConstraint(
            "(operation='PATCH' AND prototype_state='ACTIVE') OR "
            "(operation='ARCHIVE' AND prototype_state='ARCHIVED')",
            name="ck_prt_prototype_command_results__shape",
        ),
        sa.CheckConstraint("lock_version>0",
                           name="ck_prt_prototype_command_results__version"),
        schema="plm",
    )
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_prt_prototype_command_results__immutable "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.prt_prototype_command_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_prototype_command_result()"
    )
    op.execute(
        "CREATE TRIGGER trg_prt_prototype_command_results__no_truncate "
        "BEFORE TRUNCATE ON plm.prt_prototype_command_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_prototype_command_result_truncate()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_prototypes__mutation_closure AFTER UPDATE "
        "ON plm.prt_prototypes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_mutation_closure()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype mutation downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_prototype_command_results)"
    )).scalar_one():
        raise RuntimeError("Prototype mutation history prevents downgrade")
    op.execute("DROP TRIGGER trg_prt_prototypes__mutation_closure ON plm.prt_prototypes")
    op.execute(
        "DROP TRIGGER trg_prt_prototype_command_results__immutable "
        "ON plm.prt_prototype_command_results"
    )
    op.execute(
        "DROP TRIGGER trg_prt_prototype_command_results__no_truncate "
        "ON plm.prt_prototype_command_results"
    )
    op.drop_table("prt_prototype_command_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_command_result()")
    op.execute("DROP FUNCTION plm.assert_prototype_mutation_closure()")
    op.execute("DROP FUNCTION plm.reject_prototype_command_result_truncate()")
    op.execute(_DOWN_GUARD)
