"""Open only the controlled Installation Owner's append-only inserts."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20261104_0226"
down_revision = "20261104_0225"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP = 'INSERT' "
        "AND TG_TABLE_NAME IN ('plg_installations','plg_runtime_validations') "
        "AND current_setting('plm.plugin_installation_owner_write', true) = 'on' "
        "THEN RETURN NEW; END IF; "
        "RAISE EXCEPTION 'PluginInstallation Owner write is not authorized'; END; $$"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PluginInstallation Owner downgrade is disabled")
    bind = op.get_bind()
    for table in ("plg_installations", "plg_runtime_validations"):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("PluginInstallation history prevents downgrade")
    op.execute(
        "CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'PluginInstallation Owner is not installed'; END; $$"
    )
