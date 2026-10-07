"""Add evidence-backed Requirement state decision history.

Revision ID: 20261007_0114
Revises: 20261007_0113
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0114"
down_revision = "20261007_0113"
branch_labels = None
depends_on = None

_TABLES = ("req_requirement_state_decisions", "req_requirement_decision_evidence_refs")

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_state_decision_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Requirement state decision Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_state_decision_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Requirement state decision history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "req_requirement_state_decisions",
        sa.Column("decision_id", ident, primary_key=True),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("decision_type", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("decided_by", ident, nullable=False),
        sa.Column("decided_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("before_version", sa.BigInteger(), nullable=False),
        sa.Column("after_version", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("decision_id", "requirement_id", "project_id",
                            name="uq_req_state_decisions__id_requirement_project"),
        sa.UniqueConstraint("requirement_id", "after_version",
                            name="uq_req_state_decisions__requirement_version"),
        sa.ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_state_decisions__requirement", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["decided_by"], ["plm.auth_users.user_id"],
                                name="fk_req_state_decisions__actor", ondelete="NO ACTION"),
        sa.CheckConstraint("decision_type IN ('DEFER','REJECT')",
                           name="ck_req_state_decisions__type"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
                           name="ck_req_state_decisions__reason"),
        sa.CheckConstraint("char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
                           name="ck_req_state_decisions__impact"),
        sa.CheckConstraint("before_version>=0 AND after_version=before_version+1",
                           name="ck_req_state_decisions__version"),
        schema="plm",
    )
    op.create_table(
        "req_requirement_decision_evidence_refs",
        sa.Column("decision_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("decision_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.UniqueConstraint("decision_id", "evidence_id",
                            name="uq_req_decision_evidence_refs__decision_evidence"),
        sa.ForeignKeyConstraint(
            ["decision_id", "requirement_id", "project_id"],
            ["plm.req_requirement_state_decisions.decision_id",
             "plm.req_requirement_state_decisions.requirement_id",
             "plm.req_requirement_state_decisions.project_id"],
            name="fk_req_decision_evidence_refs__decision", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_req_decision_evidence_refs__evidence", ondelete="NO ACTION"),
        schema="plm",
    )
    op.create_index("ix_req_decision_evidence_refs__evidence",
                    "req_requirement_decision_evidence_refs",
                    ["evidence_id", "decision_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} "
            "FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_state_decision_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_requirement_state_decision_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Requirement state-decision downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("Requirement state decision history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_state_decision_foundation()")
    op.execute("DROP FUNCTION plm.reject_requirement_state_decision_truncate()")
