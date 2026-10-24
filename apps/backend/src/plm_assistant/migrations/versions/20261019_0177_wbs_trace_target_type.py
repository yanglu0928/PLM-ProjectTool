"""Allow a fixed WBS Item as an additive protected TraceLink endpoint.

Revision ID: 20261019_0177
Revises: 20261019_0176
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261019_0177"
down_revision = "20261019_0176"
branch_labels = None
depends_on = None


_PAIR_TEMPLATE = (
    "({role}_owner_module='document' AND {role}_object_type='DOC-02') OR "
    "({role}_owner_module='capability' AND {role}_object_type='CAP-02') OR "
    "({role}_owner_module='handover' AND {role}_object_type='HND-02') OR "
    "({role}_owner_module='survey' AND {role}_object_type IN ('SRV-02','SRV-05')) OR "
    "({role}_owner_module='requirement' AND {role}_object_type='REQ-03') OR "
    "({role}_owner_module='prototype' AND {role}_object_type IN ('PRT-03','PRT-04')) OR "
    "({role}_owner_module='solution' AND {role}_object_type IN "
    "('SOL-01','SOL-03','SOL-05','SOL-06')) OR "
    "({role}_owner_module='plan' AND {role}_object_type IN ({plan_types})) OR "
    "({role}_owner_module='output' AND {role}_object_type='OUT-02')"
)


def _replace_endpoint_checks(*, include_wbs: bool) -> None:
    plan_types = ("'PLN-02','PLN-02-WBS','PLN-03'" if include_wbs
                  else "'PLN-02','PLN-03'")
    for role in ("source", "target"):
        name = f"ck_trc_links__{role}_type"
        op.drop_constraint(name, "trc_links", schema="plm", type_="check")
        op.create_check_constraint(
            name, "trc_links",
            f"({_PAIR_TEMPLATE.format(role=role, plan_types=plan_types)})",
            schema="plm")


def upgrade() -> None:
    _replace_endpoint_checks(include_wbs=True)
    op.create_check_constraint(
        "ck_trc_links__wbs_project_scope", "trc_links",
        "NOT ((source_owner_module='plan' AND source_object_type='PLN-02-WBS') "
        "OR (target_owner_module='plan' AND target_object_type='PLN-02-WBS')) "
        "OR scope='PROJECT'", schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline WBS Trace type downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.trc_links "
        "WHERE (source_owner_module='plan' AND source_object_type='PLN-02-WBS') "
        "OR (target_owner_module='plan' AND target_object_type='PLN-02-WBS'))"
    )).scalar_one():
        raise RuntimeError("WBS TraceLink history prevents downgrade")
    op.drop_constraint("ck_trc_links__wbs_project_scope", "trc_links",
                       schema="plm", type_="check")
    _replace_endpoint_checks(include_wbs=False)
