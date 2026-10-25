"""Add closed typed JSONB snapshot for SOL-06 versions.

Revision ID: 20261012_0163
Revises: 20261012_0162
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261012_0163"
down_revision = "20261012_0162"
branch_labels = None
depends_on = None

TABLE = "sol_spec_payloads"


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        TABLE,
        sa.Column("structured_solution_spec_id", ident, primary_key=True),
        sa.Column("spec_series_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("spec_type", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id", "spec_type"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id",
             "plm.sol_structured_specs.spec_type"],
            name="fk_sol_spec_payloads__spec", ondelete="NO ACTION"),
        sa.CheckConstraint("schema_version=1", name="ck_sol_spec_payloads__schema_version"),
        sa.CheckConstraint("jsonb_typeof(payload_json)='object' AND payload_json<>'{}'::jsonb",
                           name="ck_sol_spec_payloads__object"),
        sa.CheckConstraint("octet_length(payload_json::text)<=1048576",
                           name="ck_sol_spec_payloads__size"),
        sa.CheckConstraint("octet_length(payload_fingerprint)=32",
                           name="ck_sol_spec_payloads__fingerprint"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_sol_spec_payloads__created_at"),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_structured_spec_payload_closed()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'StructuredSolutionSpec payload Owner is not installed';
        END; $$
    """)
    op.execute("""
        CREATE FUNCTION plm.reject_structured_spec_payload_truncate()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'StructuredSolutionSpec payload history cannot be truncated';
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_sol_spec_payloads__owner
        BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_spec_payloads
        FOR EACH ROW EXECUTE FUNCTION plm.guard_structured_spec_payload_closed()
    """)
    op.execute("""
        CREATE TRIGGER trg_sol_spec_payloads__no_truncate
        BEFORE TRUNCATE ON plm.sol_spec_payloads FOR EACH STATEMENT
        EXECUTE FUNCTION plm.reject_structured_spec_payload_truncate()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline StructuredSolutionSpec payload downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_spec_payloads)"
    )).scalar_one():
        raise RuntimeError("StructuredSolutionSpec payload history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_spec_payloads__owner ON plm.sol_spec_payloads")
    op.execute("DROP TRIGGER trg_sol_spec_payloads__no_truncate ON plm.sol_spec_payloads")
    op.drop_table(TABLE, schema="plm")
    op.execute("DROP FUNCTION plm.guard_structured_spec_payload_closed()")
    op.execute("DROP FUNCTION plm.reject_structured_spec_payload_truncate()")
