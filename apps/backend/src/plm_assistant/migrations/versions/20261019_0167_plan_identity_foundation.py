"""Add closed PLN-01 project Plan identity.

Revision ID: 20261019_0167
Revises: 20261019_0166
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0167"
down_revision = "20261019_0166"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan identity Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plan_identity_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan identity history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "pln_plans",
        sa.Column("plan_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("plan_state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("plan_id", "project_id", name="uq_pln_plans__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_pln_plans__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_pln_plans__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                           name="ck_pln_plans__name"),
        sa.CheckConstraint("plan_state IN ('ACTIVE','ARCHIVED')", name="ck_pln_plans__state"),
        sa.CheckConstraint("current_approved_version_ref IS NULL",
                           name="ck_pln_plans__approved_pointer_closed"),
        sa.CheckConstraint("lock_version>=0", name="ck_pln_plans__lock"),
        schema="plm",
    )
    op.create_index("ix_pln_plans__project_state", "pln_plans",
                    ["project_id", "plan_state", "plan_id"], schema="plm")
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_plans__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_plans FOR EACH ROW EXECUTE FUNCTION plm.guard_plan_identity_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_plans__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_plans FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plan_identity_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan identity downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM plm.pln_plans)")).scalar_one():
        raise RuntimeError("Plan identity history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_plans__owner ON plm.pln_plans")
    op.execute("DROP TRIGGER trg_pln_plans__no_truncate ON plm.pln_plans")
    op.drop_index("ix_pln_plans__project_state", table_name="pln_plans", schema="plm")
    op.drop_table("pln_plans", schema="plm")
    op.execute("DROP FUNCTION plm.guard_plan_identity_foundation()")
    op.execute("DROP FUNCTION plm.reject_plan_identity_truncate()")
