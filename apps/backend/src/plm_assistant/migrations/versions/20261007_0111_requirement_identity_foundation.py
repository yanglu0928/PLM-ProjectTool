"""Add REQ-01/REQ-02 package and requirement identity foundation.

Revision ID: 20261007_0111
Revises: 20261007_0110
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0111"
down_revision = "20261007_0110"
branch_labels = None
depends_on = None


_TABLES = ("req_packages", "req_requirements", "req_package_memberships")

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_identity_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Requirement identity Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='req_packages' THEN
    IF NEW.package_state<>'ACTIVE' OR NEW.lock_version<>0
       OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'RequirementPackage initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='req_requirements' THEN
    IF NEW.requirement_state<>'ACTIVE'
       OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 OR NEW.updated_by IS NOT NULL THEN
      RAISE EXCEPTION 'Requirement initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_identity_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Requirement identity history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "req_packages",
        sa.Column(
            "requirement_package_id",
            ident,
            primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "package_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("created_by", ident, nullable=False),
        sa.Column(
            "created_at",
            timestamp,
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("updated_by", ident),
        sa.Column(
            "updated_at",
            timestamp,
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column(
            "lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.UniqueConstraint(
            "requirement_package_id",
            "project_id",
            name="uq_req_packages__id_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["plm.prj_projects.project_id"],
            name="fk_req_packages__project",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_packages__creator",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_packages__updater",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_req_packages__name",
        ),
        sa.CheckConstraint(
            "package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_req_packages__state",
        ),
        sa.CheckConstraint("lock_version>=0", name="ck_req_packages__lock"),
        schema="plm",
    )
    op.create_index(
        "ix_req_packages__project_state",
        "req_packages",
        ["project_id", "package_state", "requirement_package_id"],
        schema="plm",
    )
    op.create_table(
        "req_requirements",
        sa.Column(
            "requirement_id",
            ident,
            primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_code", sa.Text(), nullable=False),
        sa.Column("requirement_code_normalized", sa.Text(), nullable=False),
        sa.Column(
            "requirement_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column(
            "created_at",
            timestamp,
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("updated_by", ident),
        sa.Column(
            "updated_at",
            timestamp,
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column(
            "lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.UniqueConstraint(
            "requirement_id", "project_id", name="uq_req_requirements__id_project"
        ),
        sa.UniqueConstraint(
            "project_id",
            "requirement_code_normalized",
            name="uq_req_requirements__project_code",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["plm.prj_projects.project_id"],
            name="fk_req_requirements__project",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_requirements__creator",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_requirements__updater",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "char_length(requirement_code) BETWEEN 1 AND 64 "
            "AND requirement_code=btrim(requirement_code)",
            name="ck_req_requirements__code",
        ),
        sa.CheckConstraint(
            "char_length(requirement_code_normalized) BETWEEN 1 AND 64 "
            "AND requirement_code_normalized=btrim(requirement_code_normalized) "
            "AND requirement_code_normalized=upper(requirement_code)",
            name="ck_req_requirements__code_normalized",
        ),
        sa.CheckConstraint(
            "requirement_state IN ('ACTIVE','DEFERRED','REJECTED','ARCHIVED')",
            name="ck_req_requirements__state",
        ),
        sa.CheckConstraint("lock_version>=0", name="ck_req_requirements__lock"),
        schema="plm",
    )
    op.create_index(
        "ix_req_requirements__project_state",
        "req_requirements",
        ["project_id", "requirement_state", "requirement_id"],
        schema="plm",
    )
    op.create_table(
        "req_package_memberships",
        sa.Column(
            "requirement_package_membership_id",
            ident,
            primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("requirement_package_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("added_by", ident, nullable=False),
        sa.Column(
            "added_at",
            timestamp,
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.UniqueConstraint(
            "requirement_package_id",
            "requirement_id",
            name="uq_req_package_memberships__package_requirement",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_package_id", "project_id"],
            ["plm.req_packages.requirement_package_id", "plm.req_packages.project_id"],
            name="fk_req_package_memberships__package",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_package_memberships__requirement",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_package_memberships__adder",
            ondelete="NO ACTION",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_req_package_memberships__requirement",
        "req_package_memberships",
        ["requirement_id", "requirement_package_id"],
        schema="plm",
    )
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
                f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
                "plm.guard_requirement_identity_foundation()"
            )
        )
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
                f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
                "plm.reject_requirement_identity_truncate()"
            )
        )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Requirement identity downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")
        ).scalar_one():
            raise RuntimeError("Requirement identity history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_identity_foundation()")
    op.execute("DROP FUNCTION plm.reject_requirement_identity_truncate()")
