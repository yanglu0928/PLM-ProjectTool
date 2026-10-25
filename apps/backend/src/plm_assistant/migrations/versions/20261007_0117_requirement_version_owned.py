"""Add closed RequirementVersion semantic owned collections.

Revision ID: 20261007_0117
Revises: 20261007_0116
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0117"
down_revision = "20261007_0116"
branch_labels = None
depends_on = None

_TABLES = (
    "req_sources",
    "req_acceptance_criteria",
    "req_capability_assessments",
    "req_assumptions",
    "req_exclusions",
    "req_dependencies",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_owned()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementVersion owned collection Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_version_owned_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementVersion owned collection history cannot be truncated';
END; $$;
"""


def _version_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["requirement_version_id", "requirement_id", "project_id"],
        ["plm.req_requirement_versions.requirement_version_id",
         "plm.req_requirement_versions.requirement_id",
         "plm.req_requirement_versions.project_id"],
        name=name, ondelete="NO ACTION",
    )


def _common_columns(id_name: str) -> list[sa.Column]:
    ident = postgresql.UUID(as_uuid=True)
    return [
        sa.Column(id_name, ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
    ]


def _install_guards() -> None:
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW "
            "EXECUTE FUNCTION plm.guard_requirement_version_owned()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION plm.reject_requirement_version_owned_truncate()"
        )


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "req_sources",
        *_common_columns("requirement_source_id"),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_object_id", ident, nullable=False),
        sa.Column("source_version_ref", ident),
        sa.UniqueConstraint(
            "requirement_source_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_sources__id_version_requirement_project"),
        sa.UniqueConstraint("requirement_version_id", "ordinal",
                            name="uq_req_sources__version_ordinal"),
        sa.UniqueConstraint("requirement_version_id", "source_type", "source_object_id",
                            name="uq_req_sources__version_source"),
        _version_fk("fk_req_sources__version"),
        sa.CheckConstraint("ordinal>=0", name="ck_req_sources__ordinal"),
        sa.CheckConstraint(
            "source_type IN ('APPROVED_SURVEY_CONCLUSION','CONFIRMED_HANDOVER',"
            "'HUMAN_DECISION','PROJECT_EVIDENCE')", name="ck_req_sources__type"),
        sa.CheckConstraint(
            "(source_type='CONFIRMED_HANDOVER' AND source_version_ref IS NOT NULL) OR "
            "(source_type<>'CONFIRMED_HANDOVER' AND source_version_ref IS NULL)",
            name="ck_req_sources__shape"),
        schema="plm",
    )
    op.create_index("ix_req_sources__version_ordinal", "req_sources",
                    ["requirement_version_id", "ordinal"], schema="plm")

    op.create_table(
        "req_acceptance_criteria",
        *_common_columns("acceptance_criterion_id"),
        sa.Column("observable_result", sa.Text(), nullable=False),
        sa.Column("verification_method", sa.Text(), nullable=False),
        sa.Column("required_data", sa.Text(), nullable=False),
        sa.Column("required_environment", sa.Text(), nullable=False),
        sa.Column("evidence_requirement", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "acceptance_criterion_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_acceptance__id_version_requirement_project"),
        sa.UniqueConstraint("requirement_version_id", "ordinal",
                            name="uq_req_acceptance__version_ordinal"),
        _version_fk("fk_req_acceptance__version"),
        sa.CheckConstraint("ordinal>=0", name="ck_req_acceptance__ordinal"),
        sa.CheckConstraint(
            "char_length(observable_result) BETWEEN 1 AND 4000 AND observable_result=btrim(observable_result) "
            "AND char_length(verification_method) BETWEEN 1 AND 4000 AND verification_method=btrim(verification_method) "
            "AND char_length(required_data) BETWEEN 1 AND 4000 AND required_data=btrim(required_data) "
            "AND char_length(required_environment) BETWEEN 1 AND 4000 AND required_environment=btrim(required_environment) "
            "AND char_length(evidence_requirement) BETWEEN 1 AND 4000 AND evidence_requirement=btrim(evidence_requirement)",
            name="ck_req_acceptance__texts"),
        schema="plm",
    )
    op.create_index("ix_req_acceptance__version_ordinal", "req_acceptance_criteria",
                    ["requirement_version_id", "ordinal"], schema="plm")

    op.create_table(
        "req_capability_assessments",
        *_common_columns("capability_assessment_id"),
        sa.Column("baseline_version_id", ident, nullable=False),
        sa.Column("capability_item_id", ident, nullable=False),
        sa.Column("match_type", sa.Text(), nullable=False),
        sa.Column("fit_gap", sa.Text(), nullable=False),
        sa.Column("constraints_text", sa.Text(), nullable=False),
        sa.Column("assessor_kind", sa.Text(), nullable=False),
        sa.Column("assessed_by", ident),
        sa.Column("assessed_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False),
        sa.Column("confirmation_state", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "capability_assessment_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_assessments__id_version_requirement_project"),
        sa.UniqueConstraint("requirement_version_id", "ordinal",
                            name="uq_req_assessments__version_ordinal"),
        sa.UniqueConstraint("requirement_version_id", "baseline_version_id",
                            "capability_item_id",
                            name="uq_req_assessments__version_capability"),
        _version_fk("fk_req_assessments__version"),
        sa.ForeignKeyConstraint(
            ["baseline_version_id", "capability_item_id"],
            ["plm.cap_items.baseline_version_id", "plm.cap_items.capability_item_id"],
            name="fk_req_assessments__capability", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["assessed_by"], ["plm.auth_users.user_id"],
                                name="fk_req_assessments__assessor",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_req_assessments__ordinal"),
        sa.CheckConstraint("match_type IN ('DIRECT','PARTIAL','NONE','UNKNOWN')",
                           name="ck_req_assessments__match"),
        sa.CheckConstraint("confirmation_state IN ('CANDIDATE','CONFIRMED','REJECTED')",
                           name="ck_req_assessments__confirmation"),
        sa.CheckConstraint(
            "(assessor_kind='HUMAN' AND assessed_by IS NOT NULL) OR "
            "(assessor_kind='AI_CANDIDATE' AND assessed_by IS NULL "
            "AND confirmation_state='CANDIDATE')",
            name="ck_req_assessments__assessor_shape"),
        sa.CheckConstraint(
            "char_length(fit_gap) BETWEEN 1 AND 4000 AND fit_gap=btrim(fit_gap) "
            "AND char_length(constraints_text) BETWEEN 1 AND 4000 "
            "AND constraints_text=btrim(constraints_text)",
            name="ck_req_assessments__texts"),
        schema="plm",
    )
    op.create_index("ix_req_assessments__version_ordinal", "req_capability_assessments",
                    ["requirement_version_id", "ordinal"], schema="plm")
    op.create_index("ix_req_assessments__capability", "req_capability_assessments",
                    ["baseline_version_id", "capability_item_id"], schema="plm")

    for table, id_name, text_name, prefix in (
        ("req_assumptions", "requirement_assumption_id", "assumption_text", "assumptions"),
        ("req_exclusions", "requirement_exclusion_id", "exclusion_text", "exclusions"),
        ("req_dependencies", "requirement_dependency_id", "dependency_text", "dependencies"),
    ):
        op.create_table(
            table,
            *_common_columns(id_name),
            sa.Column(text_name, sa.Text(), nullable=False),
            sa.UniqueConstraint(
                id_name, "requirement_version_id", "requirement_id", "project_id",
                name=f"uq_req_{prefix}__id_version_requirement_project"),
            sa.UniqueConstraint("requirement_version_id", "ordinal",
                                name=f"uq_req_{prefix}__version_ordinal"),
            _version_fk(f"fk_req_{prefix}__version"),
            sa.CheckConstraint("ordinal>=0", name=f"ck_req_{prefix}__ordinal"),
            sa.CheckConstraint(
                f"char_length({text_name}) BETWEEN 1 AND 4000 "
                f"AND {text_name}=btrim({text_name})",
                name=f"ck_req_{prefix}__text"),
            schema="plm",
        )
        op.create_index(f"ix_req_{prefix}__version_ordinal", table,
                        ["requirement_version_id", "ordinal"], schema="plm")
    _install_guards()


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RequirementVersion owned downgrade is disabled")
    bind = op.get_bind()
    if any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _TABLES):
        raise RuntimeError("RequirementVersion owned history prevents downgrade")
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_version_owned()")
    op.execute("DROP FUNCTION plm.reject_requirement_version_owned_truncate()")
