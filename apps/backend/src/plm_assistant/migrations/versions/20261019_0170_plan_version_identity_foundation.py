"""Add closed PLN-02 PlanVersion identity, retaining the null approved pointer.

Revision ID: 20261019_0170
Revises: 20261019_0169
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0170"
down_revision = "20261019_0169"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PlanVersion Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plan_version_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PlanVersion history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "pln_plan_versions",
        sa.Column("plan_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("plan_version_id", "plan_id", "project_id",
                            name="uq_pln_plan_versions__id_plan_project"),
        sa.UniqueConstraint("plan_id", "version_no",
                            name="uq_pln_plan_versions__plan_no"),
        sa.ForeignKeyConstraint(
            ["plan_id", "project_id"], ["plm.pln_plans.plan_id", "plm.pln_plans.project_id"],
            name="fk_pln_plan_versions__plan", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["supersedes_version_ref", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_plan_versions__supersedes", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_pln_plan_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_pln_plan_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_pln_plan_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_pln_plan_versions__number"),
        sa.CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
            name="ck_pln_plan_versions__state"),
        sa.CheckConstraint("supersedes_version_ref IS NULL OR "
                           "supersedes_version_ref<>plan_version_id",
                           name="ck_pln_plan_versions__supersedes_not_self"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                           "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                           name="ck_pln_plan_versions__review_pair"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_pln_plan_versions__created_at"),
        schema="plm",
    )
    op.create_index("ix_pln_plan_versions__plan_created", "pln_plan_versions",
                    ["plan_id", "created_at"], schema="plm")
    op.create_foreign_key(
        "fk_pln_plans__approved_version", "pln_plans", "pln_plan_versions",
        ["current_approved_version_ref", "plan_id", "project_id"],
        ["plan_version_id", "plan_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_plan_versions__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_plan_versions FOR EACH ROW EXECUTE FUNCTION plm.guard_plan_version_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_plan_versions__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_plan_versions FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plan_version_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PlanVersion downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_plan_versions)"
    )).scalar_one():
        raise RuntimeError("PlanVersion history prevents downgrade")
    op.drop_constraint("fk_pln_plans__approved_version", "pln_plans",
                       type_="foreignkey", schema="plm")
    op.execute("DROP TRIGGER trg_pln_plan_versions__owner ON plm.pln_plan_versions")
    op.execute("DROP TRIGGER trg_pln_plan_versions__no_truncate ON plm.pln_plan_versions")
    op.drop_index("ix_pln_plan_versions__plan_created",
                  table_name="pln_plan_versions", schema="plm")
    op.drop_table("pln_plan_versions", schema="plm")
    op.execute("DROP FUNCTION plm.guard_plan_version_foundation()")
    op.execute("DROP FUNCTION plm.reject_plan_version_truncate()")
