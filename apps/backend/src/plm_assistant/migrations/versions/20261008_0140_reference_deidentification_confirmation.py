"""Add closed GLOBAL Reference human-deidentification confirmation ledger.

Revision ID: 20261008_0140
Revises: 20261008_0139
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0140"
down_revision = "20261008_0139"
branch_labels = None
depends_on = None

TABLE = "sol_reference_deidentification_confirmations"
GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_deidentification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Reference deidentification Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_solution_reference_deidentification_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Reference deidentification history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        TABLE,
        sa.Column("confirmation_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("source_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("source_project_class", sa.Text(), nullable=False),
        sa.Column("deidentification_class", sa.Text(), nullable=False),
        sa.Column("applicability", postgresql.JSONB(), nullable=False),
        sa.Column("attestation_statement", sa.Text(), nullable=False),
        sa.Column("confirmed_by", ident, nullable=False),
        sa.Column("confirmed_at", timestamp, nullable=False),
        sa.Column("expires_at", timestamp, nullable=False),
        sa.Column("revoked_at", timestamp),
        sa.Column("trace_id", ident, nullable=False),
        sa.ForeignKeyConstraint(["confirmed_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_reference_deidentification__actor", ondelete="NO ACTION"),
        sa.CheckConstraint("octet_length(source_fingerprint)=32",
                           name="ck_sol_reference_deidentification__fingerprint"),
        sa.CheckConstraint("char_length(source_project_class) BETWEEN 1 AND 128 AND "
                           "source_project_class=btrim(source_project_class)",
                           name="ck_sol_reference_deidentification__source_class"),
        sa.CheckConstraint("char_length(deidentification_class) BETWEEN 1 AND 128 AND "
                           "deidentification_class=btrim(deidentification_class)",
                           name="ck_sol_reference_deidentification__class"),
        sa.CheckConstraint("jsonb_typeof(applicability)='object'",
                           name="ck_sol_reference_deidentification__applicability"),
        sa.CheckConstraint("attestation_statement='I_VERIFIED_DEIDENTIFICATION'",
                           name="ck_sol_reference_deidentification__statement"),
        sa.CheckConstraint("confirmed_at<expires_at AND isfinite(confirmed_at) AND "
                           "isfinite(expires_at) AND (revoked_at IS NULL OR "
                           "(revoked_at>=confirmed_at AND isfinite(revoked_at)))",
                           name="ck_sol_reference_deidentification__time"),
        schema="plm",
    )
    op.create_index("ix_sol_reference_deidentification__source", TABLE,
                    ["source_fingerprint", "expires_at", "confirmation_id"], schema="plm")
    op.execute(GUARDS)
    op.execute(sa.text(
        f"CREATE TRIGGER trg_{TABLE}__owner BEFORE INSERT OR UPDATE OR DELETE "
        f"ON plm.{TABLE} FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_reference_deidentification()"
    ))
    op.execute(sa.text(
        f"CREATE TRIGGER trg_{TABLE}__no_truncate BEFORE TRUNCATE ON plm.{TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_solution_reference_deidentification_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference deidentification downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{TABLE})")).scalar_one():
        raise RuntimeError("Reference deidentification history prevents downgrade")
    op.execute(sa.text(f"DROP TRIGGER trg_{TABLE}__owner ON plm.{TABLE}"))
    op.execute(sa.text(f"DROP TRIGGER trg_{TABLE}__no_truncate ON plm.{TABLE}"))
    op.drop_table(TABLE, schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_reference_deidentification()")
    op.execute("DROP FUNCTION plm.reject_solution_reference_deidentification_truncate()")
