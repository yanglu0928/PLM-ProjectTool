"""Project, department and member roots with scoped foreign keys.

Revision ID: 20260925_0013
Revises: 20260925_0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0013"
down_revision = "20260925_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prj_projects",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("project_code", sa.Text(), nullable=False),
        sa.Column("project_code_normalized", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("project_code_normalized", name="uq_prj_projects__code_norm"),
        sa.CheckConstraint("char_length(project_code) BETWEEN 1 AND 64", name="ck_prj_projects__code"),
        sa.CheckConstraint("char_length(project_code_normalized) BETWEEN 1 AND 64 AND project_code_normalized = btrim(project_code_normalized)", name="ck_prj_projects__code_norm"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255", name="ck_prj_projects__name"),
        sa.CheckConstraint("state IN ('ACTIVE','ARCHIVED')", name="ck_prj_projects__state"),
        sa.CheckConstraint("lock_version >= 0", name="ck_prj_projects__lock_version"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_prj_projects__created_by", ondelete="NO ACTION"),
        schema="plm",
    )
    op.create_index("ix_prj_projects__state_updated", "prj_projects", ["state", sa.text("updated_at DESC"), sa.text("project_id DESC")], schema="plm")
    op.create_index("ix_prj_projects__created_by", "prj_projects", ["created_by"], schema="plm")
    op.create_table(
        "prj_departments",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_code", sa.Text(), nullable=False),
        sa.Column("department_code_normalized", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("department_id", "project_id", name="uq_prj_departments__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_prj_departments__project", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(department_code) BETWEEN 1 AND 64", name="ck_prj_departments__code"),
        sa.CheckConstraint("char_length(department_code_normalized) BETWEEN 1 AND 64 AND department_code_normalized = btrim(department_code_normalized)", name="ck_prj_departments__code_norm"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255", name="ck_prj_departments__name"),
        sa.CheckConstraint("state IN ('ACTIVE','INACTIVE')", name="ck_prj_departments__state"),
        sa.CheckConstraint("lock_version >= 0", name="ck_prj_departments__lock_version"),
        schema="plm",
    )
    op.create_index("uq_prj_departments__project_code_live", "prj_departments", ["project_id", "department_code_normalized"], unique=True, postgresql_where=sa.text("state = 'ACTIVE'"), schema="plm")
    op.create_index("ix_prj_departments__project_state", "prj_departments", ["project_id", "state", sa.text("updated_at DESC"), sa.text("department_id DESC")], schema="plm")
    op.create_table(
        "prj_project_members",
        sa.Column("project_member_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_role", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("effective_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("project_member_id", "project_id", name="uq_prj_members__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_prj_members__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["user_id"], ["plm.auth_users.user_id"], name="fk_prj_members__user", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["department_id", "project_id"], ["plm.prj_departments.department_id", "plm.prj_departments.project_id"], name="fk_prj_members__department_project", ondelete="NO ACTION"),
        sa.CheckConstraint("project_role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_members__role"),
        sa.CheckConstraint("state IN ('ACTIVE','SUSPENDED','REMOVED')", name="ck_prj_members__state"),
        sa.CheckConstraint("(state = 'REMOVED' AND ended_at IS NOT NULL) OR (state <> 'REMOVED' AND ended_at IS NULL)", name="ck_prj_members__ended_shape"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= effective_at", name="ck_prj_members__time"),
        sa.CheckConstraint("lock_version >= 0", name="ck_prj_members__lock_version"),
        schema="plm",
    )
    op.create_index("uq_prj_members__user_active", "prj_project_members", ["user_id"], unique=True, postgresql_where=sa.text("state <> 'REMOVED'"), schema="plm")
    op.create_index("uq_prj_members__project_user_active", "prj_project_members", ["project_id", "user_id"], unique=True, postgresql_where=sa.text("state <> 'REMOVED'"), schema="plm")
    op.create_index("ix_prj_members__project_state", "prj_project_members", ["project_id", "state", sa.text("updated_at DESC"), sa.text("project_member_id DESC")], schema="plm")
    op.create_index("ix_prj_members__department_project", "prj_project_members", ["department_id", "project_id"], schema="plm")
    op.create_index("ix_prj_members__user", "prj_project_members", ["user_id"], schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Project downgrade requires a live database")
    connection = op.get_bind()
    for table in ("prj_project_members", "prj_departments", "prj_projects"):
        if connection.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")):
            raise RuntimeError("Project downgrade requires empty Project tables")
    op.drop_table("prj_project_members", schema="plm")
    op.drop_table("prj_departments", schema="plm")
    op.drop_table("prj_projects", schema="plm")
