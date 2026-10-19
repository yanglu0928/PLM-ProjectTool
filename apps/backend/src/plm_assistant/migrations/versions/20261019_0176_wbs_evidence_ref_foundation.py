"""Add closed WBS Evidence refs with proven Scope and Project.

Revision ID: 20261019_0176
Revises: 20261019_0175
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0176"
down_revision = "20261019_0175"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_wbs_evidence_ref_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsEvidenceRef Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_wbs_evidence_ref_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsEvidenceRef history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    op.create_unique_constraint("uq_evd_evidence__id_scope", "evd_evidence_records",
                                ["evidence_id", "scope"], schema="plm")
    op.create_unique_constraint("uq_evd_evidence__id_project", "evd_evidence_records",
                                ["evidence_id", "project_id"], schema="plm")
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "pln_item_evidence_refs",
        sa.Column("item_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("wbs_item_id", ident, nullable=False),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("source_scope", sa.Text(), nullable=False),
        sa.Column("source_project_id", ident),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("wbs_item_id", "evidence_id",
                            name="uq_pln_item_evidence__item_evidence"),
        sa.UniqueConstraint("wbs_item_id", "ordinal",
                            name="uq_pln_item_evidence__item_ordinal"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_evidence__wbs", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["evidence_id", "source_scope"],
            ["plm.evd_evidence_records.evidence_id", "plm.evd_evidence_records.scope"],
            name="fk_pln_item_evidence__scope", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["evidence_id", "source_project_id"],
            ["plm.evd_evidence_records.evidence_id", "plm.evd_evidence_records.project_id"],
            name="fk_pln_item_evidence__project", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "(source_scope='GLOBAL' AND source_project_id IS NULL) OR "
            "(source_scope='PROJECT' AND source_project_id IS NOT NULL "
            "AND source_project_id=project_id)",
            name="ck_pln_item_evidence__scope_project"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_item_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_pln_item_evidence__target", "pln_item_evidence_refs",
                    ["evidence_id", "project_id", "plan_version_id"], schema="plm")
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_item_evidence_refs__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_item_evidence_refs FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_wbs_evidence_ref_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_item_evidence_refs__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_item_evidence_refs FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_wbs_evidence_ref_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline WbsEvidenceRef downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_item_evidence_refs)"
    )).scalar_one():
        raise RuntimeError("WbsEvidenceRef history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_item_evidence_refs__owner "
               "ON plm.pln_item_evidence_refs")
    op.execute("DROP TRIGGER trg_pln_item_evidence_refs__no_truncate "
               "ON plm.pln_item_evidence_refs")
    op.drop_index("ix_pln_item_evidence__target",
                  table_name="pln_item_evidence_refs", schema="plm")
    op.drop_table("pln_item_evidence_refs", schema="plm")
    op.drop_constraint("uq_evd_evidence__id_project", "evd_evidence_records",
                       schema="plm", type_="unique")
    op.drop_constraint("uq_evd_evidence__id_scope", "evd_evidence_records",
                       schema="plm", type_="unique")
    op.execute("DROP FUNCTION plm.guard_wbs_evidence_ref_foundation()")
    op.execute("DROP FUNCTION plm.reject_wbs_evidence_ref_truncate()")
