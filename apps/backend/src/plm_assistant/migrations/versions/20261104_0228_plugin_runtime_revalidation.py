"""Allow validated runtime refresh and fail-closed incompatibility transitions."""
from __future__ import annotations
from alembic import context, op
import sqlalchemy as sa
revision="20261104_0228"
down_revision="20261104_0227"
branch_labels=None
depends_on=None

_UPGRADE_GUARD = """
CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF current_setting('plm.plugin_installation_owner_write', true) = 'on' THEN
IF TG_TABLE_NAME = 'plg_installations' THEN
IF TG_OP = 'INSERT' THEN RETURN NEW; END IF;
IF TG_OP = 'UPDATE'
AND NEW.plugin_installation_id = OLD.plugin_installation_id
AND NEW.plugin_package_id = OLD.plugin_package_id
AND NEW.plugin_id_normalized = OLD.plugin_id_normalized
AND NEW.installed_by = OLD.installed_by AND NEW.installed_at = OLD.installed_at
AND NEW.created_at = OLD.created_at AND NEW.created_by = OLD.created_by
AND NEW.retention_policy_id IS NOT DISTINCT FROM OLD.retention_policy_id
AND NEW.retention_due_at IS NOT DISTINCT FROM OLD.retention_due_at
AND NEW.lock_version = OLD.lock_version + 1
AND NEW.updated_by IS NOT NULL AND isfinite(NEW.updated_at)
AND NEW.installation_state IN ('INSTALLED','ENABLED','DISABLED','INCOMPATIBLE')
AND OLD.installation_state IN ('INSTALLED','ENABLED','DISABLED','INCOMPATIBLE')
AND (NEW.installation_state <> 'ENABLED' OR
     (NEW.enabled_by IS NOT NULL AND NEW.enabled_at IS NOT NULL))
AND (NEW.validated_runtime_snapshot = OLD.validated_runtime_snapshot OR EXISTS (
    SELECT 1 FROM plm.plg_runtime_validations rv
    WHERE rv.plugin_installation_id = OLD.plugin_installation_id
      AND rv.runtime_snapshot = NEW.validated_runtime_snapshot
      AND rv.validated_by = NEW.updated_by
))
AND (NEW.installation_state <> 'INCOMPATIBLE' OR (
    NOT EXISTS (SELECT 1 FROM plm.plg_enabled_operations eo
                WHERE eo.plugin_installation_id = OLD.plugin_installation_id)
    AND EXISTS (SELECT 1 FROM plm.plg_runtime_validations rv
                WHERE rv.plugin_installation_id = OLD.plugin_installation_id
                  AND rv.compatibility_state = 'INCOMPATIBLE'
                  AND rv.runtime_snapshot = NEW.validated_runtime_snapshot
                  AND rv.validated_by = NEW.updated_by)
))
AND (OLD.installation_state <> 'INCOMPATIBLE' OR
     NEW.installation_state <> 'DISABLED' OR EXISTS (
    SELECT 1 FROM plm.plg_runtime_validations rv
    WHERE rv.plugin_installation_id = OLD.plugin_installation_id
      AND rv.compatibility_state = 'COMPATIBLE'
      AND rv.runtime_snapshot = NEW.validated_runtime_snapshot
      AND rv.validated_by = NEW.updated_by
))
THEN RETURN NEW; END IF;
ELSIF TG_TABLE_NAME = 'plg_enabled_operations' AND TG_OP IN ('INSERT','DELETE') THEN
IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
ELSIF TG_TABLE_NAME IN ('plg_runtime_validations','plg_enabled_operation_history')
AND TG_OP = 'INSERT' THEN RETURN NEW; END IF; END IF;
RAISE EXCEPTION 'PluginInstallation Owner write is not authorized'; END; $$
"""
_DOWNGRADE_GUARD = """
CREATE OR REPLACE FUNCTION plm.reject_plugin_installation_write()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF current_setting('plm.plugin_installation_owner_write', true) = 'on' THEN
IF TG_TABLE_NAME = 'plg_installations' THEN
IF TG_OP = 'INSERT' THEN RETURN NEW; END IF;
IF TG_OP = 'UPDATE' AND NEW.plugin_installation_id = OLD.plugin_installation_id
AND NEW.plugin_package_id = OLD.plugin_package_id
AND NEW.plugin_id_normalized = OLD.plugin_id_normalized
AND NEW.installed_by = OLD.installed_by AND NEW.installed_at = OLD.installed_at
AND NEW.validated_runtime_snapshot = OLD.validated_runtime_snapshot
AND NEW.created_at = OLD.created_at AND NEW.created_by = OLD.created_by
AND NEW.retention_policy_id IS NOT DISTINCT FROM OLD.retention_policy_id
AND NEW.retention_due_at IS NOT DISTINCT FROM OLD.retention_due_at
AND NEW.lock_version = OLD.lock_version + 1
AND NEW.updated_by IS NOT NULL AND isfinite(NEW.updated_at)
AND NEW.installation_state IN ('ENABLED','DISABLED')
AND OLD.installation_state IN ('INSTALLED','DISABLED','ENABLED')
AND (NEW.installation_state <> 'ENABLED' OR
     (NEW.enabled_by IS NOT NULL AND NEW.enabled_at IS NOT NULL))
THEN RETURN NEW; END IF;
ELSIF TG_TABLE_NAME = 'plg_enabled_operations' AND TG_OP IN ('INSERT','DELETE') THEN
IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
ELSIF TG_TABLE_NAME IN ('plg_runtime_validations','plg_enabled_operation_history')
AND TG_OP = 'INSERT' THEN RETURN NEW; END IF; END IF;
RAISE EXCEPTION 'PluginInstallation Owner write is not authorized'; END; $$
"""
def upgrade() -> None:
    op.execute(_UPGRADE_GUARD)

def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plugin runtime revalidation downgrade is disabled")
    bind=op.get_bind()
    for table in ("plg_enabled_operation_history","plg_enabled_operations",
                  "plg_runtime_validations","plg_installations"):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("PluginInstallation runtime history prevents downgrade")
    op.execute(_DOWNGRADE_GUARD)
