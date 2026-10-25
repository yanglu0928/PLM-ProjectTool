"""Add four closed owned reference collections for SOL-06 versions.

Revision ID: 20261012_0162
Revises: 20261012_0161
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261012_0162"
down_revision = "20261012_0161"
branch_labels = None
depends_on = None

_TABLES = (
    "sol_spec_requirement_refs", "sol_spec_section_refs",
    "sol_spec_evidence_refs", "sol_spec_artifact_refs",
)

_GUARDS = r"""
CREATE FUNCTION plm.guard_structured_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'StructuredSolutionSpec reference Owner is not installed';
END; $$;

CREATE FUNCTION plm.reject_structured_spec_refs_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'StructuredSolutionSpec reference history cannot be truncated';
END; $$;
"""


def _base_columns(pk: str) -> list[sa.Column]:
    ident = postgresql.UUID(as_uuid=True)
    return [
        sa.Column(pk, ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("structured_solution_spec_id", ident, nullable=False),
        sa.Column("spec_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
    ]


def _spec_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["structured_solution_spec_id", "spec_series_id", "project_id"],
        ["plm.sol_structured_specs.structured_solution_spec_id",
         "plm.sol_structured_specs.spec_series_id",
         "plm.sol_structured_specs.project_id"],
        name=name, ondelete="NO ACTION")


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_spec_requirement_refs",
        *_base_columns("spec_requirement_ref_id"),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        _spec_fk("fk_sol_spec_requirements__spec"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_sol_spec_requirements__requirement", ondelete="NO ACTION"),
        sa.UniqueConstraint("structured_solution_spec_id", "ordinal",
                            name="uq_sol_spec_requirements__version_ordinal"),
        sa.UniqueConstraint("structured_solution_spec_id", "requirement_id",
                            name="uq_sol_spec_requirements__version_requirement"),
        sa.UniqueConstraint("structured_solution_spec_id", "requirement_version_id",
                            name="uq_sol_spec_requirements__version_req_version"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_spec_requirements__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_spec_requirements__target", "sol_spec_requirement_refs",
                    ["requirement_version_id", "structured_solution_spec_id"], schema="plm")

    op.create_table(
        "sol_spec_section_refs",
        *_base_columns("spec_section_ref_id"),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("solution_section_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        _spec_fk("fk_sol_spec_sections__spec"),
        sa.ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_sol_spec_sections__section", ondelete="NO ACTION"),
        sa.UniqueConstraint("structured_solution_spec_id", "ordinal",
                            name="uq_sol_spec_sections__version_ordinal"),
        sa.UniqueConstraint("structured_solution_spec_id", "solution_section_id",
                            name="uq_sol_spec_sections__version_section"),
        sa.UniqueConstraint("structured_solution_spec_id", "solution_section_version_id",
                            name="uq_sol_spec_sections__version_section_version"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_spec_sections__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_spec_sections__target", "sol_spec_section_refs",
                    ["solution_section_version_id", "structured_solution_spec_id"], schema="plm")

    op.create_table(
        "sol_spec_evidence_refs",
        *_base_columns("spec_evidence_ref_id"),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        _spec_fk("fk_sol_spec_evidence__spec"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_sol_spec_evidence__evidence", ondelete="NO ACTION"),
        sa.UniqueConstraint("structured_solution_spec_id", "ordinal",
                            name="uq_sol_spec_evidence__version_ordinal"),
        sa.UniqueConstraint("structured_solution_spec_id", "evidence_id",
                            name="uq_sol_spec_evidence__version_evidence"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_spec_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_spec_evidence__target", "sol_spec_evidence_refs",
                    ["evidence_id", "structured_solution_spec_id"], schema="plm")

    op.create_table(
        "sol_spec_artifact_refs",
        *_base_columns("spec_artifact_ref_id"),
        sa.Column("output_artifact_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        _spec_fk("fk_sol_spec_artifacts__spec"),
        sa.UniqueConstraint("structured_solution_spec_id", "ordinal",
                            name="uq_sol_spec_artifacts__version_ordinal"),
        sa.UniqueConstraint("structured_solution_spec_id", "output_artifact_id",
                            name="uq_sol_spec_artifacts__version_artifact"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_spec_artifacts__ordinal"),
        sa.CheckConstraint(
            "output_artifact_id<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_sol_spec_artifacts__identity"),
        schema="plm",
    )
    op.create_index("ix_sol_spec_artifacts__target", "sol_spec_artifact_refs",
                    ["output_artifact_id", "structured_solution_spec_id"], schema="plm")

    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner "
            f"BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} "
            "FOR EACH ROW EXECUTE FUNCTION plm.guard_structured_spec_refs_closed()"))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate "
            f"BEFORE TRUNCATE ON plm.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION plm.reject_structured_spec_refs_truncate()"))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline StructuredSolutionSpec refs downgrade is disabled")
    bind = op.get_bind()
    if any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _TABLES):
        raise RuntimeError("StructuredSolutionSpec reference history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}__owner ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_structured_spec_refs_closed()")
    op.execute("DROP FUNCTION plm.reject_structured_spec_refs_truncate()")
