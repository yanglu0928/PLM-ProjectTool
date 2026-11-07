"""Add closed PLG-03 PluginExecution persistence foundations."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261105_0231"
down_revision = "20261104_0230"
branch_labels = None
depends_on = None


_WRITE_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_plugin_execution_owner_write()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'plg_executions'
     AND current_setting('plm.plugin_execution_owner_write', true) = 'on'
     AND TG_OP IN ('INSERT','UPDATE')
  THEN
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME <> 'plg_executions'
     AND TG_OP = 'INSERT'
     AND current_setting('plm.plugin_execution_owner_write', true) = 'on'
  THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'PluginExecution persistence is owner controlled and append only';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plugin_execution_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PluginExecution history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    ts = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "plg_executions",
        sa.Column("plugin_execution_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("output_request_id", ident, nullable=False),
        sa.Column("output_context_snapshot_id", ident, nullable=False),
        sa.Column("plugin_installation_id", ident, nullable=False),
        sa.Column("plugin_package_id", ident, nullable=False),
        sa.Column("plugin_id_normalized", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("context_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("job_id", ident, nullable=False),
        sa.Column("attempt_no", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("execution_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("result_manifest_ref", sa.Text()),
        sa.Column("result_fingerprint", sa.LargeBinary()),
        sa.Column("error_code", sa.Text()),
        sa.Column("retryable", sa.Boolean()),
        sa.Column("started_at", ts),
        sa.Column("completed_at", ts),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("created_at", ts, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("retention_policy_id", ident),
        sa.Column("retention_due_at", ts),
        sa.UniqueConstraint("plugin_execution_id", "project_id",
                            name="uq_plg_executions__id_project"),
        sa.UniqueConstraint("project_id", "idempotency_key",
                            name="uq_plg_executions__project_idempotency"),
        sa.UniqueConstraint("job_id", name="uq_plg_executions__job"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_plg_executions__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["output_request_id", "project_id"],
            ["plm.out_output_requests.output_request_id",
             "plm.out_output_requests.project_id"],
            name="fk_plg_executions__output_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["output_context_snapshot_id", "project_id"],
            ["plm.out_context_snapshots.context_snapshot_id",
             "plm.out_context_snapshots.project_id"],
            name="fk_plg_executions__context_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["plugin_installation_id", "plugin_package_id", "plugin_id_normalized"],
            ["plm.plg_installations.plugin_installation_id",
             "plm.plg_installations.plugin_package_id",
             "plm.plg_installations.plugin_id_normalized"],
            name="fk_plg_executions__installation_package", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["plugin_package_id", "operation_id"],
            ["plm.plg_manifest_operations.plugin_package_id",
             "plm.plg_manifest_operations.operation_id"],
            name="fk_plg_executions__manifest_operation", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["plm.job_jobs.job_id"],
            name="fk_plg_executions__job", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "char_length(operation_id) BETWEEN 1 AND 255 "
            "AND operation_id = btrim(operation_id)",
            name="ck_plg_executions__operation"),
        sa.CheckConstraint("attempt_no > 0", name="ck_plg_executions__attempt"),
        sa.CheckConstraint("octet_length(context_fingerprint) = 32",
                           name="ck_plg_executions__context_hash"),
        sa.CheckConstraint(
            "execution_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_plg_executions__state"),
        sa.CheckConstraint("lock_version >= 0", name="ck_plg_executions__lock_version"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 200 "
            "AND idempotency_key = btrim(idempotency_key)",
            name="ck_plg_executions__idempotency"),
        sa.CheckConstraint(
            "(execution_state='PENDING' AND started_at IS NULL AND completed_at IS NULL) OR "
            "(execution_state='RUNNING' AND started_at IS NOT NULL AND completed_at IS NULL) OR "
            "(execution_state IN ('SUCCEEDED','FAILED') AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(execution_state='CANCELLED' AND completed_at IS NOT NULL)",
            name="ck_plg_executions__time_shape"),
        sa.CheckConstraint(
            "(error_code IS NULL AND retryable IS NULL) OR "
            "(execution_state='FAILED' AND error_code IS NOT NULL AND retryable IS NOT NULL "
            "AND error_code ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_plg_executions__error_shape"),
        sa.CheckConstraint(
            "(execution_state='SUCCEEDED' AND result_manifest_ref IS NOT NULL "
            "AND result_manifest_ref !~ '(^/|^[A-Za-z]:|[\\\\])' "
            "AND result_fingerprint IS NOT NULL "
            "AND octet_length(result_fingerprint)=32) OR "
            "(execution_state<>'SUCCEEDED' AND result_manifest_ref IS NULL "
            "AND result_fingerprint IS NULL)",
            name="ck_plg_executions__result_shape"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_plg_executions__created_at"),
        sa.CheckConstraint("started_at IS NULL OR isfinite(started_at)",
                           name="ck_plg_executions__started_at"),
        sa.CheckConstraint("completed_at IS NULL OR isfinite(completed_at)",
                           name="ck_plg_executions__completed_at"),
        schema="plm",
    )
    op.create_index(
        "ix_plg_executions__project_state_created", "plg_executions",
        ["project_id", "execution_state", "created_at", "plugin_execution_id"],
        schema="plm")
    op.create_table(
        "plg_execution_result_files",
        sa.Column("result_file_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plugin_execution_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("file_object_id", ident, nullable=False),
        sa.Column("file_scope", sa.Text(), nullable=False,
                  server_default=sa.text("'PROJECT'")),
        sa.Column("relative_name", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", ts, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("plugin_execution_id", "project_id", "relative_name",
                            name="uq_plg_exec_result_files__execution_name"),
        sa.UniqueConstraint("file_object_id", name="uq_plg_exec_result_files__file"),
        sa.ForeignKeyConstraint(
            ["plugin_execution_id", "project_id"],
            ["plm.plg_executions.plugin_execution_id", "plm.plg_executions.project_id"],
            name="fk_plg_exec_result_files__execution_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["file_object_id", "file_scope", "project_id"],
            ["plm.doc_file_objects.file_object_id", "plm.doc_file_objects.scope",
             "plm.doc_file_objects.project_id"],
            name="fk_plg_exec_result_files__file_project", ondelete="NO ACTION"),
        sa.CheckConstraint("file_scope = 'PROJECT'",
                           name="ck_plg_exec_result_files__scope"),
        sa.CheckConstraint(
            "char_length(relative_name) BETWEEN 1 AND 255 "
            "AND relative_name=btrim(relative_name) "
            "AND relative_name !~ '(^/|^[A-Za-z]:|[\\\\])' "
            "AND relative_name !~ '(^|/)\\.\\.(/|$)'",
            name="ck_plg_exec_result_files__relative_name"),
        sa.CheckConstraint("char_length(media_type) BETWEEN 1 AND 255",
                           name="ck_plg_exec_result_files__mime"),
        sa.CheckConstraint("octet_length(sha256) = 32",
                           name="ck_plg_exec_result_files__sha256"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_plg_exec_result_files__size"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_plg_exec_result_files__created_at"),
        schema="plm",
    )
    op.create_index(
        "ix_plg_exec_result_files__execution", "plg_execution_result_files",
        ["plugin_execution_id", "project_id", "created_at", "result_file_id"],
        schema="plm")
    op.create_table(
        "plg_execution_state_events",
        sa.Column("state_event_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plugin_execution_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("from_state", sa.Text()),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text()),
        sa.Column("actor_id", ident),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("created_at", ts, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["plugin_execution_id", "project_id"],
            ["plm.plg_executions.plugin_execution_id", "plm.plg_executions.project_id"],
            name="fk_plg_exec_state_events__execution_project", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state IN "
            "('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_plg_exec_state_events__from_state"),
        sa.CheckConstraint(
            "to_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_plg_exec_state_events__to_state"),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name="ck_plg_exec_state_events__reason"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_plg_exec_state_events__created_at"),
        schema="plm",
    )
    op.create_index(
        "ix_plg_exec_state_events__execution", "plg_execution_state_events",
        ["plugin_execution_id", "project_id", "created_at", "state_event_id"],
        schema="plm")

    op.execute(_WRITE_GUARD)
    for table in ("plg_executions", "plg_execution_result_files",
                  "plg_execution_state_events"):
        op.execute(f"""
        CREATE TRIGGER trg_{table}__owner_write
        BEFORE INSERT OR UPDATE OR DELETE ON plm.{table}
        FOR EACH ROW EXECUTE FUNCTION plm.guard_plugin_execution_owner_write()
        """)
        op.execute(f"""
        CREATE TRIGGER trg_{table}__no_truncate
        BEFORE TRUNCATE ON plm.{table}
        FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plugin_execution_truncate()
        """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PluginExecution downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.plg_executions) "
        "OR EXISTS (SELECT 1 FROM plm.plg_execution_result_files) "
        "OR EXISTS (SELECT 1 FROM plm.plg_execution_state_events)"
    )).scalar_one():
        raise RuntimeError("PluginExecution history blocks downgrade")
    for table in ("plg_executions", "plg_execution_result_files",
                  "plg_execution_state_events"):
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__owner_write ON plm.{table}")
    op.execute("DROP FUNCTION plm.reject_plugin_execution_truncate()")
    op.execute("DROP FUNCTION plm.guard_plugin_execution_owner_write()")
    op.drop_table("plg_execution_state_events", schema="plm")
    op.drop_index("ix_plg_exec_result_files__execution", table_name="plg_execution_result_files", schema="plm")
    op.drop_table("plg_execution_result_files", schema="plm")
    op.drop_index("ix_plg_executions__project_state_created", table_name="plg_executions", schema="plm")
    op.drop_table("plg_executions", schema="plm")
