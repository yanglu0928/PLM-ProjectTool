"""Add closed SOL-06 immutable StructuredSolutionSpec version identity.

Revision ID: 20261012_0161
Revises: 20261009_0160
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261012_0161"
down_revision = "20261009_0160"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_structured_solution_spec_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'StructuredSolutionSpec write Owner is not installed';
END; $$;

CREATE FUNCTION plm.reject_structured_solution_spec_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'StructuredSolutionSpec history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_structured_specs",
        sa.Column("structured_solution_spec_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("spec_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("spec_type", sa.Text(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("structured_solution_spec_id", "spec_series_id", "project_id",
                            name="uq_sol_specs__id_series_project"),
        sa.UniqueConstraint("structured_solution_spec_id", "spec_series_id", "project_id",
                            "spec_type", name="uq_sol_specs__id_series_project_type"),
        sa.UniqueConstraint("spec_series_id", "version_no", name="uq_sol_specs__series_no"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_sol_specs__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_specs__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["supersedes_version_ref", "spec_series_id", "project_id", "spec_type"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id",
             "plm.sol_structured_specs.spec_type"],
            name="fk_sol_specs__supersedes", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_sol_specs__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_sol_specs__round", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "spec_series_id<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_sol_specs__series"),
        sa.CheckConstraint("version_no>0", name="ck_sol_specs__number"),
        sa.CheckConstraint(
            "spec_type IN ('PROCESS_MODEL','INTERFACE_SPEC','MIGRATION_SPEC',"
            "'PERMISSION_DESIGN')", name="ck_sol_specs__type"),
        sa.CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_sol_specs__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_sol_specs__fingerprint"),
        sa.CheckConstraint(
            "supersedes_version_ref IS NULL OR "
            "supersedes_version_ref<>structured_solution_spec_id",
            name="ck_sol_specs__supersedes_not_self"),
        sa.CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_sol_specs__review_pair"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_sol_specs__created_at"),
        schema="plm",
    )
    op.create_index("ix_sol_specs__series_created", "sol_structured_specs",
                    ["spec_series_id", "created_at"], schema="plm")
    op.create_index("ix_sol_specs__project_type", "sol_structured_specs",
                    ["project_id", "spec_type", "version_state"], schema="plm")
    op.execute(_GUARDS)
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_specs__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_structured_specs "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_structured_solution_spec_closed()"))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_specs__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_structured_specs FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_structured_solution_spec_truncate()"))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline StructuredSolutionSpec downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_structured_specs)"
    )).scalar_one():
        raise RuntimeError("StructuredSolutionSpec history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_specs__owner ON plm.sol_structured_specs")
    op.execute("DROP TRIGGER trg_sol_specs__no_truncate ON plm.sol_structured_specs")
    op.drop_index("ix_sol_specs__project_type", table_name="sol_structured_specs",
                  schema="plm")
    op.drop_index("ix_sol_specs__series_created", table_name="sol_structured_specs",
                  schema="plm")
    op.drop_table("sol_structured_specs", schema="plm")
    op.execute("DROP FUNCTION plm.guard_structured_solution_spec_closed()")
    op.execute("DROP FUNCTION plm.reject_structured_solution_spec_truncate()")
