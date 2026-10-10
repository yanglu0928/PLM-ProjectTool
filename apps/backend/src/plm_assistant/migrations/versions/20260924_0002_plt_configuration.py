"""PLT-01 configuration identity and immutable versions."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0002"
down_revision = "20260924_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plt_system_configurations",
        sa.Column("system_configuration_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("config_key", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'INACTIVE'")),
        sa.Column("active_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("retention_policy_id", postgresql.UUID(as_uuid=True)),
        sa.Column("retention_due_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("config_key"),
        sa.CheckConstraint("config_key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$' AND char_length(config_key) <= 64", name="ck_plt_system_configurations__config_key_format"),
        sa.CheckConstraint("state IN ('ACTIVE', 'INACTIVE')", name="ck_plt_system_configurations__state"),
        sa.CheckConstraint("lock_version >= 0", name="ck_plt_system_configurations__lock_version"),
        schema="plm",
    )
    op.create_table(
        "plt_configuration_versions",
        sa.Column("configuration_version_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("system_configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False),
        sa.Column("supersedes_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("value_type", sa.Text(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["system_configuration_id"], ["plm.plt_system_configurations.system_configuration_id"], name="fk_plt_cfg_ver__config", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_id", "system_configuration_id"], ["plm.plt_configuration_versions.configuration_version_id", "plm.plt_configuration_versions.system_configuration_id"], name="fk_plt_cfg_ver__supersedes", ondelete="NO ACTION"),
        sa.UniqueConstraint("system_configuration_id", "version_no"),
        sa.UniqueConstraint("configuration_version_id", "system_configuration_id"),
        sa.CheckConstraint("version_no > 0", name="ck_plt_configuration_versions__version_no"),
        sa.CheckConstraint("version_state IN ('ACTIVE', 'INACTIVE')", name="ck_plt_configuration_versions__version_state"),
        sa.CheckConstraint("value_type IN ('STRING', 'INTEGER', 'BOOLEAN', 'JSON')", name="ck_plt_configuration_versions__value_type"),
        sa.CheckConstraint("octet_length(content_fingerprint) = 32", name="ck_plt_configuration_versions__content_fingerprint"),
        sa.CheckConstraint("(value_type = 'STRING' AND jsonb_typeof(value_json) = 'string') OR (value_type = 'INTEGER' AND jsonb_typeof(value_json) = 'number') OR (value_type = 'BOOLEAN' AND jsonb_typeof(value_json) = 'boolean') OR (value_type = 'JSON' AND jsonb_typeof(value_json) IN ('object', 'array'))", name="ck_plt_configuration_versions__value_shape"),
        schema="plm",
    )
    op.create_foreign_key(
        "fk_plt_cfg__active_version",
        "plt_system_configurations", "plt_configuration_versions",
        ["active_version_id", "system_configuration_id"],
        ["configuration_version_id", "system_configuration_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
    )
    op.execute("""
        CREATE FUNCTION plm.reject_configuration_version_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'configuration versions are immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_plt_configuration_versions_immutable
        BEFORE UPDATE OR DELETE ON plm.plt_configuration_versions
        FOR EACH ROW EXECUTE FUNCTION plm.reject_configuration_version_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: configuration data must be checked")
    bind = op.get_bind()
    for table_name in ("plt_configuration_versions", "plt_system_configurations"):
        count = bind.scalar(sa.text(f"SELECT count(*) FROM plm.{table_name}"))
        if count:
            raise RuntimeError("configuration data exists; restore from backup before downgrade")
    op.execute("DROP TRIGGER trg_plt_configuration_versions_immutable ON plm.plt_configuration_versions")
    op.execute("DROP FUNCTION plm.reject_configuration_version_mutation()")
    op.drop_constraint("fk_plt_cfg__active_version", "plt_system_configurations", schema="plm", type_="foreignkey")
    op.drop_table("plt_configuration_versions", schema="plm")
    op.drop_table("plt_system_configurations", schema="plm")
