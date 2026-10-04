"""Append-only ProjectMember role/department change history.

Revision ID: 20260925_0014
Revises: 20260925_0013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0014"
down_revision = "20260925_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prj_member_assignment_history",
        sa.Column("history_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("project_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("before_role", sa.Text(), nullable=False),
        sa.Column("after_role", sa.Text(), nullable=False),
        sa.Column("before_department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("after_department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("before_version", sa.BigInteger(), nullable=False),
        sa.Column("after_version", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["project_member_id", "project_id"], ["plm.prj_project_members.project_member_id", "plm.prj_project_members.project_id"], name="fk_prj_assignment_history__member_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["plm.auth_users.user_id"], name="fk_prj_assignment_history__actor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["before_department_id", "project_id"], ["plm.prj_departments.department_id", "plm.prj_departments.project_id"], name="fk_prj_assignment_history__before_department", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["after_department_id", "project_id"], ["plm.prj_departments.department_id", "plm.prj_departments.project_id"], name="fk_prj_assignment_history__after_department", ondelete="NO ACTION"),
        sa.UniqueConstraint("project_member_id", "after_version", name="uq_prj_assignment_history__member_version"),
        sa.CheckConstraint("before_role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_assignment_history__before_role"),
        sa.CheckConstraint("after_role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_assignment_history__after_role"),
        sa.CheckConstraint("after_version = before_version + 1 AND before_version >= 0", name="ck_prj_assignment_history__version"),
        sa.CheckConstraint("before_role <> after_role OR before_department_id <> after_department_id", name="ck_prj_assignment_history__changed"),
        schema="plm",
    )
    op.create_index("ix_prj_assignment_history__project_member", "prj_member_assignment_history", ["project_id", "project_member_id", sa.text("changed_at DESC")], schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("assignment history downgrade requires a live database")
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.prj_member_assignment_history)")):
        raise RuntimeError("assignment history downgrade requires an empty history table")
    op.drop_table("prj_member_assignment_history", schema="plm")
