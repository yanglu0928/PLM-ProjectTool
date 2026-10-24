"""Add closed fixed ReferenceVersion links to SolutionOutlineVersion.

Revision ID: 20261009_0154
Revises: 20261009_0153
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0154"
down_revision = "20261009_0153"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_unique_constraint(
        "uq_sol_reference_versions__id_parent_scope_project",
        "sol_reference_versions",
        ["reference_version_id", "reference_solution_id", "scope", "project_id"],
        schema="plm",
    )
    op.add_column(
        "sol_outline_versions",
        sa.Column("declared_reference_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        schema="plm",
    )
    op.create_check_constraint(
        "ck_sol_outline_versions__reference_count", "sol_outline_versions",
        "declared_reference_count>=0", schema="plm",
    )
    op.create_table(
        "sol_outline_reference_refs",
        sa.Column("solution_outline_reference_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_outline_version_id", ident, nullable=False),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("reference_version_id", ident, nullable=False),
        sa.Column("reference_scope", sa.Text(), nullable=False),
        sa.Column("source_project_id", ident),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("solution_outline_version_id", "ordinal",
                            name="uq_sol_outline_references__version_ordinal"),
        sa.UniqueConstraint("solution_outline_version_id", "reference_version_id",
                            name="uq_sol_outline_references__version_reference"),
        sa.ForeignKeyConstraint(
            ["solution_outline_version_id", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_sol_outline_references__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["reference_version_id", "reference_solution_id", "reference_scope"],
            ["plm.sol_reference_versions.reference_version_id",
             "plm.sol_reference_versions.reference_solution_id",
             "plm.sol_reference_versions.scope"],
            name="fk_sol_outline_references__reference", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["reference_version_id", "reference_solution_id", "reference_scope", "source_project_id"],
            ["plm.sol_reference_versions.reference_version_id",
             "plm.sol_reference_versions.reference_solution_id",
             "plm.sol_reference_versions.scope", "plm.sol_reference_versions.project_id"],
            name="fk_sol_outline_references__project_source", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_outline_references__ordinal"),
        sa.CheckConstraint(
            "(reference_scope='PROJECT' AND source_project_id=project_id) OR "
            "(reference_scope='GLOBAL' AND source_project_id IS NULL)",
            name="ck_sol_outline_references__scope_project"),
        schema="plm",
    )
    op.create_index(
        "ix_sol_outline_references__target", "sol_outline_reference_refs",
        ["reference_version_id", "solution_outline_version_id"], schema="plm",
    )
    # The shared 0137 guard remains closed; adding only this table's triggers
    # never authorizes creation of any SolutionOutlineVersion or its references.
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_outline_reference_refs__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_outline_reference_refs "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_outline_version_foundation()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_outline_reference_refs__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_outline_reference_refs FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_outline_version_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Outline reference downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outline_reference_refs)"
    )).scalar_one():
        raise RuntimeError("Outline reference history prevents downgrade")
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outline_versions "
        "WHERE declared_reference_count<>0)"
    )).scalar_one():
        raise RuntimeError("Outline reference count history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_outline_reference_refs__owner ON plm.sol_outline_reference_refs")
    op.execute("DROP TRIGGER trg_sol_outline_reference_refs__no_truncate ON plm.sol_outline_reference_refs")
    op.drop_index("ix_sol_outline_references__target", table_name="sol_outline_reference_refs", schema="plm")
    op.drop_table("sol_outline_reference_refs", schema="plm")
    op.drop_constraint("ck_sol_outline_versions__reference_count", "sol_outline_versions",
                       type_="check", schema="plm")
    op.drop_column("sol_outline_versions", "declared_reference_count", schema="plm")
    op.drop_constraint("uq_sol_reference_versions__id_parent_scope_project", "sol_reference_versions",
                       type_="unique", schema="plm")
