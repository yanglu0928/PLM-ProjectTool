"""Persist immutable first-success Department deactivation projections.

Revision ID: 20260925_0019
Revises: 20260925_0018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0019"
down_revision = "20260925_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prj_department_deactivate_results",
        sa.Column("result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_prj_department_deactivate_results__department_project", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("char_length(code) BETWEEN 1 AND 64", name="ck_prj_department_deactivate_results__code"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255", name="ck_prj_department_deactivate_results__name"),
        sa.CheckConstraint("lock_version > 0", name="ck_prj_department_deactivate_results__version"),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.reject_department_deactivate_result_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'department deactivate result is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_prj_department_deactivate_results_immutable
        BEFORE UPDATE OR DELETE ON plm.prj_department_deactivate_results
        FOR EACH ROW EXECUTE FUNCTION plm.reject_department_deactivate_result_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for department deactivate results")
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prj_department_deactivate_results)"
    )):
        raise RuntimeError("department deactivate results exist; downgrade refused")
    op.execute("DROP TRIGGER trg_prj_department_deactivate_results_immutable ON plm.prj_department_deactivate_results")
    op.execute("DROP FUNCTION plm.reject_department_deactivate_result_mutation()")
    op.drop_table("prj_department_deactivate_results", schema="plm")
