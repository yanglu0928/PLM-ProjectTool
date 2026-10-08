"""Add SOL-02/SOL-04 project-scoped identity foundation.

Revision ID: 20261008_0136
Revises: 20261008_0135
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0136"
down_revision = "20261008_0135"
branch_labels = None
depends_on = None

_TABLES = ("sol_outlines", "sol_sections")
_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Solution identity Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_solution_identity_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Solution identity history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "sol_outlines",
        sa.Column("solution_outline_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("outline_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("solution_outline_id", "project_id", name="uq_sol_outlines__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_sol_outlines__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_outlines__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                           name="ck_sol_outlines__name"),
        sa.CheckConstraint("outline_state IN ('ACTIVE','ARCHIVED')", name="ck_sol_outlines__state"),
        sa.CheckConstraint("lock_version>=0", name="ck_sol_outlines__lock"),
        schema="plm",
    )
    op.create_index("ix_sol_outlines__project_state", "sol_outlines",
                    ["project_id", "outline_state", "solution_outline_id"], schema="plm")
    op.create_table(
        "sol_sections",
        sa.Column("solution_section_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("section_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("solution_section_id", "project_id", name="uq_sol_sections__id_project"),
        sa.UniqueConstraint("solution_outline_id", "section_key", name="uq_sol_sections__outline_key"),
        sa.ForeignKeyConstraint(["solution_outline_id", "project_id"],
                                ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
                                name="fk_sol_sections__outline_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_sections__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(section_key) BETWEEN 1 AND 128 AND section_key=btrim(section_key)",
                           name="ck_sol_sections__key"),
        sa.CheckConstraint("section_state IN ('ACTIVE','ARCHIVED')", name="ck_sol_sections__state"),
        sa.CheckConstraint("lock_version>=0", name="ck_sol_sections__lock"),
        schema="plm",
    )
    op.create_index("ix_sol_sections__outline_state", "sol_sections",
                    ["solution_outline_id", "section_state", "solution_section_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_identity_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_solution_identity_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Solution identity downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Solution identity history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_identity_foundation()")
    op.execute("DROP FUNCTION plm.reject_solution_identity_truncate()")
