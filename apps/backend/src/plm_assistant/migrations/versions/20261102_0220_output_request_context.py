"""Add closed OUT-01 OutputRequest and fixed ContextSnapshot persistence."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261102_0220"
down_revision = "20261026_0210"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.reject_output_foundation_write()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'OutputRequest Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_output_foundation_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Output foundation history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "out_context_snapshots",
        sa.Column("context_snapshot_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("source_version_refs", jsonb, nullable=False),
        sa.Column("context_payload", jsonb, nullable=False),
        sa.Column("context_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("context_snapshot_id", "project_id",
                            name="uq_out_context_snapshots__id_project"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_out_context_snapshots__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_out_context_snapshots__creator", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "CASE WHEN jsonb_typeof(source_version_refs) = 'array' "
            "THEN jsonb_array_length(source_version_refs) > 0 ELSE FALSE END",
            name="ck_out_context_snapshots__sources"),
        sa.CheckConstraint("jsonb_typeof(context_payload) = 'object'",
                           name="ck_out_context_snapshots__payload"),
        sa.CheckConstraint("octet_length(context_fingerprint) = 32",
                           name="ck_out_context_snapshots__fingerprint"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_out_context_snapshots__created_at"),
        schema="plm",
    )
    op.create_index(
        "ix_out_context_snapshots__project_created",
        "out_context_snapshots",
        ["project_id", "created_at", "context_snapshot_id"],
        schema="plm",
    )
    op.create_table(
        "out_output_requests",
        sa.Column("output_request_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("output_type", sa.Text(), nullable=False),
        sa.Column("template_version_ref", ident, nullable=False),
        sa.Column("source_version_refs", jsonb, nullable=False),
        sa.Column("output_policy_ref", sa.Text(), nullable=False),
        sa.Column("plugin_operation", sa.Text(), nullable=False),
        sa.Column("context_snapshot_id", ident, nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("generation_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("request_state", sa.Text(), nullable=False,
                  server_default=sa.text("'REQUESTED'")),
        sa.Column("job_ref", ident),
        sa.Column("current_execution_ref", ident),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("requested_by", ident, nullable=False),
        sa.Column("requested_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("completed_at", timestamp),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("output_request_id", "project_id",
                            name="uq_out_output_requests__id_project"),
        sa.UniqueConstraint("project_id", "idempotency_key",
                            name="uq_out_output_requests__project_idempotency"),
        sa.UniqueConstraint(
            "project_id", "output_type", "input_fingerprint", "template_version_ref",
            "output_policy_ref", "generation_no",
            name="uq_out_output_requests__generation_identity"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_out_output_requests__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["plm.auth_users.user_id"],
            name="fk_out_output_requests__requester", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id", "project_id"],
            ["plm.out_context_snapshots.context_snapshot_id",
             "plm.out_context_snapshots.project_id"],
            name="fk_out_output_requests__context_project", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "output_type IN ('DOCX', 'PPTX', 'PNG', 'JPEG')",
            name="ck_out_output_requests__type"),
        sa.CheckConstraint(
            "request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING',"
            "'SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')",
            name="ck_out_output_requests__state"),
        sa.CheckConstraint(
            "CASE WHEN jsonb_typeof(source_version_refs) = 'array' "
            "THEN jsonb_array_length(source_version_refs) > 0 ELSE FALSE END",
            name="ck_out_output_requests__sources"),
        sa.CheckConstraint("octet_length(input_fingerprint) = 32",
                           name="ck_out_output_requests__fingerprint"),
        sa.CheckConstraint("generation_no > 0 AND lock_version >= 0",
                           name="ck_out_output_requests__generation_lock"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 200 "
            "AND idempotency_key = btrim(idempotency_key)",
            name="ck_out_output_requests__idempotency"),
        sa.CheckConstraint(
            "char_length(output_policy_ref) BETWEEN 1 AND 200 "
            "AND output_policy_ref = btrim(output_policy_ref)",
            name="ck_out_output_requests__policy"),
        sa.CheckConstraint(
            "char_length(plugin_operation) BETWEEN 1 AND 200 "
            "AND plugin_operation = btrim(plugin_operation)",
            name="ck_out_output_requests__plugin_operation"),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_out_output_requests__completed_at"),
        schema="plm",
    )
    op.create_index(
        "ix_out_output_requests__project_state_requested",
        "out_output_requests",
        ["project_id", "request_state", "requested_at", "output_request_id"],
        schema="plm",
    )
    op.execute(_GUARDS)
    for table in ("out_context_snapshots", "out_output_requests"):
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.reject_output_foundation_write()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION plm.reject_output_foundation_truncate()"
        )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Output foundation downgrade is disabled")
    bind = op.get_bind()
    has_history = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.out_output_requests) "
        "OR EXISTS (SELECT 1 FROM plm.out_context_snapshots)"
    )).scalar_one()
    if has_history:
        raise RuntimeError("Output foundation history prevents downgrade")
    for table in ("out_output_requests", "out_context_snapshots"):
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    op.drop_index(
        "ix_out_output_requests__project_state_requested",
        table_name="out_output_requests", schema="plm")
    op.drop_table("out_output_requests", schema="plm")
    op.drop_index(
        "ix_out_context_snapshots__project_created",
        table_name="out_context_snapshots", schema="plm")
    op.drop_table("out_context_snapshots", schema="plm")
    op.execute("DROP FUNCTION plm.reject_output_foundation_write()")
    op.execute("DROP FUNCTION plm.reject_output_foundation_truncate()")
