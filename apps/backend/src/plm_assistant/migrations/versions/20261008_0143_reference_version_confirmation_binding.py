"""Bind GLOBAL ReferenceVersion to the exact attested source fingerprint.

Revision ID: 20261008_0143
Revises: 20261008_0142
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0143"
down_revision = "20261008_0142"
branch_labels = None
depends_on = None

_VERSIONS = "sol_reference_versions"
_CONFIRMATIONS = "sol_reference_deidentification_confirmations"


def _require_no_versions() -> None:
    if context.is_offline_mode():
        op.execute(sa.text(
            "DO $binding_guard$ BEGIN "
            "IF EXISTS (SELECT 1 FROM plm.sol_reference_versions) THEN "
            "RAISE EXCEPTION 'ReferenceVersion history requires reviewed source binding migration'; "
            "END IF; END $binding_guard$;"))
        return
    if op.get_bind().execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM plm.{_VERSIONS})")).scalar_one():
        raise RuntimeError("ReferenceVersion history requires reviewed source binding migration")


def upgrade() -> None:
    _require_no_versions()
    op.create_unique_constraint(
        "uq_sol_reference_deidentification__id_source", _CONFIRMATIONS,
        ["confirmation_id", "source_fingerprint"], schema="plm")
    op.add_column(_VERSIONS, sa.Column("source_fingerprint", sa.LargeBinary(), nullable=False),
                  schema="plm")
    op.add_column(_VERSIONS, sa.Column("deidentification_confirmation_id",
                                       postgresql.UUID(as_uuid=True)), schema="plm")
    op.create_check_constraint(
        "ck_sol_reference_versions__source_fingerprint", _VERSIONS,
        "octet_length(source_fingerprint)=32", schema="plm")
    op.create_check_constraint(
        "ck_sol_reference_versions__confirmation_scope", _VERSIONS,
        "(scope='GLOBAL' AND deidentification_confirmation_id IS NOT NULL) OR "
        "(scope='PROJECT' AND deidentification_confirmation_id IS NULL)", schema="plm")
    op.create_foreign_key(
        "fk_sol_reference_versions__confirmation_source", _VERSIONS, _CONFIRMATIONS,
        ["deidentification_confirmation_id", "source_fingerprint"],
        ["confirmation_id", "source_fingerprint"], source_schema="plm",
        referent_schema="plm", ondelete="NO ACTION")


def downgrade() -> None:
    _require_no_versions()
    op.drop_constraint("fk_sol_reference_versions__confirmation_source", _VERSIONS,
                       type_="foreignkey", schema="plm")
    op.drop_constraint("ck_sol_reference_versions__confirmation_scope", _VERSIONS,
                       type_="check", schema="plm")
    op.drop_constraint("ck_sol_reference_versions__source_fingerprint", _VERSIONS,
                       type_="check", schema="plm")
    op.drop_column(_VERSIONS, "deidentification_confirmation_id", schema="plm")
    op.drop_column(_VERSIONS, "source_fingerprint", schema="plm")
    op.drop_constraint("uq_sol_reference_deidentification__id_source", _CONFIRMATIONS,
                       type_="unique", schema="plm")
