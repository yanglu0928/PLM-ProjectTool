"""Add immutable snapshots for idempotent PluginInstallation disable responses."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261104_0230"
down_revision = "20261104_0229"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plg_disable_results",
        sa.Column("disable_result_id", sa.UUID(as_uuid=True),
                  server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("plugin_installation_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("result_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("installation_state", sa.Text(), nullable=False),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  server_default=sa.text("statement_timestamp()"), nullable=False),
        sa.CheckConstraint("expected_lock_version >= 0",
                           name="ck_plg_disable_results__expected_version"),
        sa.CheckConstraint(
            "(changed AND result_lock_version = expected_lock_version + 1) OR "
            "(NOT changed AND result_lock_version = expected_lock_version)",
            name="ck_plg_disable_results__result_version",
        ),
        sa.CheckConstraint("installation_state = 'DISABLED'",
                           name="ck_plg_disable_results__state"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_plg_disable_results__created_at"),
        sa.ForeignKeyConstraint(
            ["plugin_installation_id"], ["plm.plg_installations.plugin_installation_id"],
            name="fk_plg_disable_results__installation", ondelete="NO ACTION",
        ),
        schema="plm",
    )
    op.execute("""
    CREATE FUNCTION plm.reject_plugin_disable_result_write()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'INSERT'
         AND current_setting('plm.plugin_installation_owner_write', true) = 'on'
      THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'PluginDisableResult is append-only and owner controlled';
    END; $$
    """)
    op.execute("""
    CREATE TRIGGER trg_plg_disable_results__owner_closed
    BEFORE INSERT OR UPDATE OR DELETE ON plm.plg_disable_results
    FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_disable_result_write()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PluginDisableResult downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.plg_disable_results)"
    )).scalar_one():
        raise RuntimeError("Plugin disable result history prevents downgrade")
    op.execute("DROP TRIGGER trg_plg_disable_results__owner_closed ON plm.plg_disable_results")
    op.execute("DROP FUNCTION plm.reject_plugin_disable_result_write()")
    op.drop_table("plg_disable_results", schema="plm")
