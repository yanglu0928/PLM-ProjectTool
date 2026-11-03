"""Open atomic Plugin activation writes and preserve immutable operation history."""
from __future__ import annotations
from alembic import context, op
import sqlalchemy as sa
revision="20261104_0227"
down_revision="20261104_0226"
branch_labels=None
depends_on=None

def upgrade() -> None:
    op.create_table("plg_enabled_operation_history",
        sa.Column("activation_history_id",sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True,server_default=sa.text("uuidv7()")),
        sa.Column("plugin_installation_id",sa.dialects.postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("plugin_package_id",sa.dialects.postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("plugin_id_normalized",sa.Text(),nullable=False),
        sa.Column("operation_id",sa.Text(),nullable=False),
        sa.Column("transition",sa.Text(),nullable=False),
        sa.Column("actor_id",sa.dialects.postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("trace_id",sa.dialects.postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("audit_event_id",sa.dialects.postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("changed_at",sa.dialects.postgresql.TIMESTAMP(timezone=True,precision=6),
                  nullable=False,server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["plugin_installation_id","plugin_package_id","plugin_id_normalized"],
            ["plm.plg_installations.plugin_installation_id","plm.plg_installations.plugin_package_id",
             "plm.plg_installations.plugin_id_normalized"],
            name="fk_plg_enabled_operation_history__installation",ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["plugin_package_id","operation_id"],
            ["plm.plg_manifest_operations.plugin_package_id","plm.plg_manifest_operations.operation_id"],
            name="fk_plg_enabled_operation_history__manifest_operation",ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["audit_event_id"],["plm.aud_events.audit_event_id"],
            name="fk_plg_enabled_operation_history__audit_event",ondelete="NO ACTION"),
        sa.CheckConstraint("transition IN ('ENABLED','DISABLED')",
            name="ck_plg_enabled_operation_history__transition"),
        sa.CheckConstraint("isfinite(changed_at)",
            name="ck_plg_enabled_operation_history__changed_at"),schema="plm")
    op.create_index("ix_plg_enabled_operation_history__plugin_operation_time",
        "plg_enabled_operation_history",
        ["plugin_id_normalized","operation_id","changed_at","activation_history_id"],schema="plm")
    op.execute(
        "CREATE OR REPLACE FUNCTION plm.reject_plugin_enabled_operation_history_mutation() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'Plugin enabled-operation history is append-only'; END; $$")
    op.execute(
        "CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF current_setting('plm.plugin_installation_owner_write', true) = 'on' THEN "
        "IF TG_TABLE_NAME = 'plg_installations' THEN "
        "IF TG_OP = 'INSERT' THEN RETURN NEW; END IF; "
        "IF TG_OP = 'UPDATE' AND NEW.plugin_installation_id = OLD.plugin_installation_id "
        "AND NEW.plugin_package_id = OLD.plugin_package_id "
        "AND NEW.plugin_id_normalized = OLD.plugin_id_normalized "
        "AND NEW.installed_by = OLD.installed_by AND NEW.installed_at = OLD.installed_at "
        "AND NEW.validated_runtime_snapshot = OLD.validated_runtime_snapshot "
        "AND NEW.created_at = OLD.created_at AND NEW.created_by = OLD.created_by "
        "AND NEW.retention_policy_id IS NOT DISTINCT FROM OLD.retention_policy_id "
        "AND NEW.retention_due_at IS NOT DISTINCT FROM OLD.retention_due_at "
        "AND NEW.lock_version = OLD.lock_version + 1 "
        "AND NEW.updated_by IS NOT NULL AND isfinite(NEW.updated_at) "
        "AND NEW.installation_state IN ('ENABLED','DISABLED') "
        "AND OLD.installation_state IN ('INSTALLED','DISABLED','ENABLED') "
        "AND (NEW.installation_state <> 'ENABLED' OR "
        "(NEW.enabled_by IS NOT NULL AND NEW.enabled_at IS NOT NULL)) "
        "THEN RETURN NEW; END IF; "
        "ELSIF TG_TABLE_NAME = 'plg_enabled_operations' AND TG_OP IN ('INSERT','DELETE') THEN "
        "IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF; "
        "ELSIF TG_TABLE_NAME IN ('plg_runtime_validations','plg_enabled_operation_history') "
        "AND TG_OP = 'INSERT' THEN RETURN NEW; END IF; END IF; "
        "RAISE EXCEPTION 'PluginInstallation Owner write is not authorized'; END; $$")
    op.execute(
        "CREATE TRIGGER trg_plg_enabled_operation_history__owner_closed "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.plg_enabled_operation_history "
        "FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_installation_write()")
    op.execute(
        "CREATE TRIGGER trg_plg_enabled_operation_history__no_truncate "
        "BEFORE TRUNCATE ON plm.plg_enabled_operation_history "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plugin_installation_truncate()")
    op.execute(
        "CREATE TRIGGER trg_plg_enabled_operation_history__immutable "
        "BEFORE UPDATE OR DELETE ON plm.plg_enabled_operation_history "
        "FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_enabled_operation_history_mutation()")

def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plugin activation downgrade is disabled")
    bind=op.get_bind()
    for table in ("plg_enabled_operation_history","plg_enabled_operations",
                  "plg_runtime_validations","plg_installations"):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("PluginInstallation history prevents downgrade")
    op.execute("DROP TRIGGER trg_plg_enabled_operation_history__immutable ON plm.plg_enabled_operation_history")
    op.execute("DROP TRIGGER trg_plg_enabled_operation_history__no_truncate ON plm.plg_enabled_operation_history")
    op.execute("DROP TRIGGER trg_plg_enabled_operation_history__owner_closed ON plm.plg_enabled_operation_history")
    op.drop_index("ix_plg_enabled_operation_history__plugin_operation_time",
                  table_name="plg_enabled_operation_history",schema="plm")
    op.drop_table("plg_enabled_operation_history",schema="plm")
    op.execute("DROP FUNCTION plm.reject_plugin_enabled_operation_history_mutation()")
    op.execute(
        "CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP = 'INSERT' AND TG_TABLE_NAME IN ('plg_installations','plg_runtime_validations') "
        "AND current_setting('plm.plugin_installation_owner_write', true) = 'on' "
        "THEN RETURN NEW; END IF; "
        "RAISE EXCEPTION 'PluginInstallation Owner write is not authorized'; END; $$")
