"""Add closed PLG-02 installation persistence tables."""
from __future__ import annotations
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261104_0225"
down_revision="20261103_0224"
branch_labels=None
depends_on=None
_TABLES=("plg_installations","plg_enabled_operations","plg_runtime_validations")

def upgrade() -> None:
    ident=postgresql.UUID(as_uuid=True); ts=postgresql.TIMESTAMP(timezone=True,precision=6)
    jsonb=postgresql.JSONB(astext_type=sa.Text())
    op.create_table("plg_installations",
        sa.Column("plugin_installation_id",ident,primary_key=True,server_default=sa.text("uuidv7()")),
        sa.Column("plugin_package_id",ident,nullable=False),sa.Column("plugin_id_normalized",sa.Text(),nullable=False),
        sa.Column("installation_state",sa.Text(),nullable=False,server_default=sa.text("'INSTALLED'")),
        sa.Column("validated_runtime_snapshot",jsonb,nullable=False),sa.Column("installed_by",ident,nullable=False),
        sa.Column("installed_at",ts,nullable=False,server_default=sa.text("statement_timestamp()")),
        sa.Column("enabled_by",ident),sa.Column("enabled_at",ts),
        sa.Column("created_at",ts,nullable=False,server_default=sa.text("statement_timestamp()")),
        sa.Column("created_by",ident,nullable=False),sa.Column("updated_at",ts,nullable=False,
        server_default=sa.text("statement_timestamp()")),sa.Column("updated_by",ident,nullable=False),
        sa.Column("lock_version",sa.BigInteger(),nullable=False,server_default=sa.text("0")),
        sa.Column("retention_policy_id",ident),sa.Column("retention_due_at",ts),
        sa.UniqueConstraint("plugin_installation_id","plugin_package_id","plugin_id_normalized",
                            name="uq_plg_installations__id_package_plugin"),
        sa.ForeignKeyConstraint(["plugin_package_id","plugin_id_normalized"],
            ["plm.plg_packages.plugin_package_id","plm.plg_packages.plugin_id_normalized"],
            name="fk_plg_installations__package_plugin",ondelete="NO ACTION"),
        sa.CheckConstraint("installation_state IN ('INSTALLED','ENABLED','DISABLED','INCOMPATIBLE','RETIRED')",
                            name="ck_plg_installations__state"),
        sa.CheckConstraint("jsonb_typeof(validated_runtime_snapshot)='object'",
                            name="ck_plg_installations__runtime_snapshot"),
        sa.CheckConstraint("(enabled_by IS NULL AND enabled_at IS NULL) OR (enabled_by IS NOT NULL AND enabled_at IS NOT NULL)",
                            name="ck_plg_installations__enabled_actor_time"),
        sa.CheckConstraint("installation_state <> 'ENABLED' OR (enabled_by IS NOT NULL AND enabled_at IS NOT NULL)",
                            name="ck_plg_installations__enabled_state_actor"),
        sa.CheckConstraint("lock_version>=0 AND isfinite(created_at) AND isfinite(updated_at) AND "
                            "isfinite(installed_at) AND (enabled_at IS NULL OR isfinite(enabled_at)) AND "
                            "(retention_due_at IS NULL OR isfinite(retention_due_at))",
                            name="ck_plg_installations__time_lock"),schema="plm")
    op.create_index("ix_plg_installations__state_created","plg_installations",
                    ["installation_state","created_at","plugin_installation_id"],schema="plm")
    op.create_table("plg_enabled_operations",
        sa.Column("plugin_installation_id",ident,nullable=False),sa.Column("operation_id",sa.Text(),nullable=False),
        sa.Column("plugin_package_id",ident,nullable=False),sa.Column("plugin_id_normalized",sa.Text(),nullable=False),
        sa.PrimaryKeyConstraint("plugin_installation_id","operation_id",name="pk_plg_enabled_operations"),
        sa.ForeignKeyConstraint(["plugin_installation_id","plugin_package_id","plugin_id_normalized"],
            ["plm.plg_installations.plugin_installation_id","plm.plg_installations.plugin_package_id",
             "plm.plg_installations.plugin_id_normalized"],
            name="fk_plg_enabled_operations__installation_package",ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["plugin_package_id","operation_id"],
            ["plm.plg_manifest_operations.plugin_package_id","plm.plg_manifest_operations.operation_id"],
            name="fk_plg_enabled_operations__manifest_operation",ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(operation_id) BETWEEN 1 AND 255 AND operation_id=btrim(operation_id)",
                           name="ck_plg_enabled_operations__operation"),schema="plm")
    op.create_index("uq_plg_enabled_operations__plugin_operation","plg_enabled_operations",
                    ["plugin_id_normalized","operation_id"],unique=True,schema="plm")
    op.create_index("ix_plg_enabled_operations__package","plg_enabled_operations",
                    ["plugin_package_id","operation_id"],schema="plm")
    op.create_table("plg_runtime_validations",
        sa.Column("runtime_validation_id",ident,primary_key=True,server_default=sa.text("uuidv7()")),
        sa.Column("plugin_installation_id",ident,nullable=False),sa.Column("compatibility_state",sa.Text(),nullable=False),
        sa.Column("runtime_snapshot",jsonb,nullable=False),sa.Column("validated_by",ident,nullable=False),
        sa.Column("validated_at",ts,nullable=False,server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["plugin_installation_id"],["plm.plg_installations.plugin_installation_id"],
            name="fk_plg_runtime_validations__installation",ondelete="NO ACTION"),
        sa.CheckConstraint("compatibility_state IN ('COMPATIBLE','INCOMPATIBLE')",
                           name="ck_plg_runtime_validations__state"),
        sa.CheckConstraint("jsonb_typeof(runtime_snapshot)='object'",
                           name="ck_plg_runtime_validations__snapshot"),
        sa.CheckConstraint("isfinite(validated_at)",name="ck_plg_runtime_validations__time"),schema="plm")
    op.create_index("ix_plg_runtime_validations__installation_time","plg_runtime_validations",
                    ["plugin_installation_id","validated_at","runtime_validation_id"],schema="plm")
    op.execute("CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write() RETURNS trigger "
               "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'PluginInstallation Owner is not installed'; END; $$")
    op.execute("CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_truncate() RETURNS trigger "
               "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'PluginInstallation history cannot be truncated'; END; $$")
    op.execute("CREATE OR REPLACE FUNCTION plm.reject_plugin_runtime_validation_mutation() RETURNS trigger "
               "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Plugin runtime validation history is append-only'; END; $$")
    for table in _TABLES:
        op.execute(f"CREATE TRIGGER trg_{table}__owner_closed BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} "
                   "FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_installation_write()")
        op.execute(f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plugin_installation_truncate()")
    op.execute("CREATE TRIGGER trg_plg_runtime_validations__immutable BEFORE UPDATE OR DELETE "
               "ON plm.plg_runtime_validations FOR EACH ROW "
               "EXECUTE FUNCTION plm.reject_plugin_runtime_validation_mutation()")

def downgrade() -> None:
    if context.is_offline_mode(): raise RuntimeError("offline PluginInstallation downgrade is disabled")
    bind=op.get_bind()
    for table in reversed(_TABLES):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("PluginInstallation history prevents downgrade")
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    op.execute("DROP TRIGGER trg_plg_runtime_validations__immutable ON plm.plg_runtime_validations")
    for idx,table in (("ix_plg_runtime_validations__installation_time","plg_runtime_validations"),
        ("ix_plg_enabled_operations__package","plg_enabled_operations"),
        ("uq_plg_enabled_operations__plugin_operation","plg_enabled_operations"),
        ("ix_plg_installations__state_created","plg_installations")):
        op.drop_index(idx,table_name=table,schema="plm")
    op.drop_table("plg_runtime_validations",schema="plm")
    op.drop_table("plg_enabled_operations",schema="plm")
    op.drop_table("plg_installations",schema="plm")
    op.execute("DROP FUNCTION plm.reject_plugin_runtime_validation_mutation()")
    op.execute("DROP FUNCTION plm.reject_plugin_installation_truncate()")
    op.execute("DROP FUNCTION plm.reject_plugin_installation_write()")
