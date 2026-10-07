"""Add immutable Requirement identity create replay snapshots.

Revision ID: 20261007_0112
Revises: 20261007_0111
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0112"
down_revision = "20261007_0111"
branch_labels = None
depends_on = None


_TABLES = ("req_package_create_results", "req_requirement_create_results")

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_create_result_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Requirement create result history is immutable';
  END IF;
  IF TG_TABLE_NAME='req_package_create_results' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.req_packages p
       WHERE p.requirement_package_id=NEW.requirement_package_id
         AND p.project_id=NEW.project_id AND p.name=NEW.name
         AND p.created_at=NEW.created_at AND p.package_state='ACTIVE'
         AND p.updated_by IS NULL AND p.lock_version=0
    ) THEN
      RAISE EXCEPTION 'Requirement create result does not match initial identity';
    END IF;
  ELSIF TG_TABLE_NAME='req_requirement_create_results' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.req_requirements r
       WHERE r.requirement_id=NEW.requirement_id
         AND r.project_id=NEW.project_id
         AND r.requirement_code=NEW.requirement_code
         AND r.created_at=NEW.created_at AND r.requirement_state='ACTIVE'
         AND r.current_approved_version_ref IS NULL AND r.lock_version=0
    ) THEN
      RAISE EXCEPTION 'Requirement create result does not match initial identity';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_create_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Requirement create result history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_check_constraint(
        "ck_req_requirements__code_pattern",
        "req_requirements",
        "requirement_code ~ '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'",
        schema="plm",
    )
    op.create_table(
        "req_package_create_results",
        sa.Column("requirement_package_id", ident, primary_key=True),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_package_id", "project_id"],
            ["plm.req_packages.requirement_package_id", "plm.req_packages.project_id"],
            name="fk_req_package_create_results__package",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_req_package_create_results__name",
        ),
        schema="plm",
    )
    op.create_table(
        "req_requirement_create_results",
        sa.Column("requirement_id", ident, primary_key=True),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_code", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_requirement_create_results__requirement",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "requirement_code ~ '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'",
            name="ck_req_requirement_create_results__code",
        ),
        schema="plm",
    )
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table}__immutable BEFORE INSERT OR UPDATE OR DELETE "
                f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
                "plm.guard_requirement_create_result_history()"
            )
        )
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
                f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
                "plm.reject_requirement_create_result_truncate()"
            )
        )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Requirement create-result downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")
        ).scalar_one():
            raise RuntimeError("Requirement create result history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__immutable ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_create_result_history()")
    op.execute("DROP FUNCTION plm.reject_requirement_create_result_truncate()")
    op.drop_constraint(
        "ck_req_requirements__code_pattern",
        "req_requirements",
        schema="plm",
        type_="check",
    )
