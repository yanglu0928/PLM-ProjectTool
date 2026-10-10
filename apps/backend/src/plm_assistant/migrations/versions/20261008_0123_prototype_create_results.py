"""Add immutable Prototype identity create replay snapshots.

Revision ID: 20261008_0123
Revises: 20261008_0122
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0123"
down_revision = "20261008_0122"
branch_labels = None
depends_on = None

_TABLES = ("prt_package_create_results", "prt_prototype_create_results")

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_create_result_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Prototype create result history is immutable';
  END IF;
  IF TG_TABLE_NAME='prt_package_create_results' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.prt_packages p
       WHERE p.prototype_package_id=NEW.prototype_package_id
         AND p.project_id=NEW.project_id AND p.name=NEW.name
         AND p.created_at=NEW.created_at AND p.package_state='ACTIVE'
         AND p.updated_by IS NULL AND p.lock_version=0
    ) THEN RAISE EXCEPTION 'Prototype create result does not match initial identity'; END IF;
  ELSE
    IF NOT EXISTS (
      SELECT 1 FROM plm.prt_prototypes p
       WHERE p.prototype_id=NEW.prototype_id
         AND p.project_id=NEW.project_id AND p.name=NEW.name
         AND p.created_at=NEW.created_at AND p.prototype_state='ACTIVE'
         AND p.current_approved_version_ref IS NULL
         AND p.updated_by IS NULL AND p.lock_version=0
    ) THEN RAISE EXCEPTION 'Prototype create result does not match initial identity'; END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_create_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='prt_packages' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.prt_package_create_results r
       WHERE r.prototype_package_id=NEW.prototype_package_id
         AND r.project_id=NEW.project_id AND r.name=NEW.name
         AND r.created_at=NEW.created_at
    ) THEN RAISE EXCEPTION 'PrototypePackage has no immutable create result'; END IF;
  ELSE
    IF NOT EXISTS (
      SELECT 1 FROM plm.prt_prototype_create_results r
       WHERE r.prototype_id=NEW.prototype_id AND r.project_id=NEW.project_id
         AND r.name=NEW.name AND r.created_at=NEW.created_at
    ) THEN RAISE EXCEPTION 'Prototype has no immutable create result'; END IF;
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_create_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Prototype create result history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    op.execute(sa.text(r"""
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM plm.prt_packages)
     OR EXISTS (SELECT 1 FROM plm.prt_prototypes) THEN
    RAISE EXCEPTION 'pre-existing Prototype identity requires audited migration';
  END IF;
END $$;
"""))
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "prt_package_create_results",
        sa.Column("prototype_package_id", ident, primary_key=True),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["prototype_package_id", "project_id"],
            ["plm.prt_packages.prototype_package_id", "plm.prt_packages.project_id"],
            name="fk_prt_package_create_results__package", ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_package_create_results__name",
        ), schema="plm",
    )
    op.create_table(
        "prt_prototype_create_results",
        sa.Column("prototype_id", ident, primary_key=True),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_prototype_create_results__prototype", ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_prototype_create_results__name",
        ), schema="plm",
    )
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__immutable BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_create_result_history()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_prototype_create_result_truncate()"
        ))
    for table in ("prt_packages", "prt_prototypes"):
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__create_closure AFTER INSERT "
            f"ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "
            "plm.assert_prototype_create_closure()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype create-result downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Prototype create result history prevents downgrade")
    for table in ("prt_packages", "prt_prototypes"):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__create_closure ON plm.{table}"))
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__immutable ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_create_result_history()")
    op.execute("DROP FUNCTION plm.assert_prototype_create_closure()")
    op.execute("DROP FUNCTION plm.reject_prototype_create_result_truncate()")
