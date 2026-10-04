"""Persist immutable first-success member-create projections.

Revision ID: 20260925_0016
Revises: 20260925_0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0016"
down_revision = "20260925_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prj_member_create_results",
        sa.Column("member_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_name", sa.Text(), nullable=False),
        sa.Column("effective_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.ForeignKeyConstraint(["member_id", "project_id"],
                                ["plm.prj_project_members.project_member_id", "plm.prj_project_members.project_id"],
                                name="fk_prj_member_create_results__member_project", ondelete="NO ACTION"),
        sa.CheckConstraint("role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_member_create_results__role"),
        sa.CheckConstraint("char_length(user_display_name) BETWEEN 1 AND 255", name="ck_prj_member_create_results__user_name"),
        sa.CheckConstraint("char_length(department_name) BETWEEN 1 AND 255", name="ck_prj_member_create_results__department_name"),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.reject_member_create_result_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'member create result is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_prj_member_create_results_immutable
        BEFORE UPDATE OR DELETE ON plm.prj_member_create_results
        FOR EACH ROW EXECUTE FUNCTION plm.reject_member_create_result_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for member create results")
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.prj_member_create_results)")):
        raise RuntimeError("member create results exist; downgrade refused")
    op.execute("DROP TRIGGER trg_prj_member_create_results_immutable ON plm.prj_member_create_results")
    op.execute("DROP FUNCTION plm.reject_member_create_result_mutation()")
    op.drop_table("prj_member_create_results", schema="plm")
