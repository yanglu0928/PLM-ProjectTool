"""Persist fixed PrototypeVersion refs for Plan WBS items.

Revision ID: 20261026_0187
Revises: 20261026_0186
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261026_0187"
down_revision = "20261026_0186"
branch_labels = None
depends_on = None

_TABLE = "pln_item_prototype_refs"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("item_prototype_ref_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("wbs_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prototype_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prototype_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("wbs_item_id", "prototype_version_id",
                            name="uq_pln_item_prototypes__item_version"),
        sa.UniqueConstraint("wbs_item_id", "ordinal",
                            name="uq_pln_item_prototypes__item_ordinal"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_prototypes__wbs", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id", "plm.prt_prototype_versions.project_id"],
            name="fk_pln_item_prototypes__prototype_version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_item_prototypes__ordinal"),
        schema="plm",
    )
    op.create_index("ix_pln_item_prototypes__project_version", _TABLE,
                    ["project_id", "plan_version_id"], schema="plm")
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}__owner BEFORE INSERT OR UPDATE OR DELETE "
        f"ON plm.{_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_snapshot_child_foundation()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}__no_truncate BEFORE TRUNCATE "
        f"ON plm.{_TABLE} FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_plan_snapshot_child_truncate()"
    )


def _has_history() -> bool:
    return bool(op.get_bind().execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{_TABLE})")).scalar_one())


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan WBS Prototype ref downgrade is disabled")
    if _has_history():
        raise RuntimeError("Plan WBS Prototype ref history prevents downgrade")
    op.execute(f"DROP TRIGGER trg_{_TABLE}__owner ON plm.{_TABLE}")
    op.execute(f"DROP TRIGGER trg_{_TABLE}__no_truncate ON plm.{_TABLE}")
    op.drop_index("ix_pln_item_prototypes__project_version", table_name=_TABLE, schema="plm")
    op.drop_table(_TABLE, schema="plm")
