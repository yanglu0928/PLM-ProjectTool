"""PostgreSQL persistence for PluginInstallation retirement."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.retirement_owner import (
    PluginInstallationRetirementContext, PluginInstallationRetirementOwnerError,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginEnabledOperationHistoryRow, PluginEnabledOperationRow,
    PluginInstallationRow, PluginPackageRow,
)


class SqlAlchemyPluginInstallationRetirementRepository:
    def identify_plugin(self, transaction: object, *,
                        installation_id: uuid.UUID) -> str | None:
        return self._session(transaction).execute(
            select(PluginInstallationRow.plugin_id_normalized).where(
                PluginInstallationRow.plugin_installation_id == installation_id)
        ).scalar_one_or_none()

    def lock_plugin(self, transaction: object, *, plugin_id: str) -> None:
        key = f"plugin-activation:{plugin_id}"
        self._session(transaction).execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0)))
        )

    def load_context(self, transaction: object, *,
                     installation_id: uuid.UUID
                     ) -> PluginInstallationRetirementContext | None:
        session = self._session(transaction)
        target = session.execute(
            select(PluginInstallationRow, PluginPackageRow.plugin_package_id)
            .join(PluginPackageRow,
                  (PluginPackageRow.plugin_package_id
                   == PluginInstallationRow.plugin_package_id)
                  & (PluginPackageRow.plugin_id_normalized
                     == PluginInstallationRow.plugin_id_normalized))
            .where(PluginInstallationRow.plugin_installation_id == installation_id)
            .with_for_update(of=[PluginInstallationRow, PluginPackageRow])
        ).first()
        if target is None:
            return None
        row, package_id = target
        operations = tuple(session.execute(
            select(PluginEnabledOperationRow.operation_id)
            .where(PluginEnabledOperationRow.plugin_installation_id == installation_id)
            .order_by(PluginEnabledOperationRow.operation_id)
            .with_for_update()
        ).scalars().all())
        return PluginInstallationRetirementContext(
            row.plugin_id_normalized, row.plugin_installation_id, package_id,
            row.installation_state, row.lock_version, operations)

    def authorize_owner_writes(self, transaction: object) -> None:
        self._session(transaction).execute(
            text("SELECT set_config('plm.plugin_installation_owner_write','on',true)")
        )

    def apply_retirement(self, transaction: object, *,
                         context: PluginInstallationRetirementContext,
                         actor_id: uuid.UUID, changed_at: datetime) -> None:
        session = self._session(transaction)
        session.execute(delete(PluginEnabledOperationRow).where(
            PluginEnabledOperationRow.plugin_installation_id
            == context.plugin_installation_id))
        result = session.execute(
            update(PluginInstallationRow)
            .where(PluginInstallationRow.plugin_installation_id
                   == context.plugin_installation_id,
                   PluginInstallationRow.lock_version == context.lock_version,
                   PluginInstallationRow.installation_state == context.installation_state)
            .values(installation_state="RETIRED", updated_by=actor_id,
                    updated_at=changed_at, lock_version=context.lock_version + 1)
        )
        if result.rowcount != 1:
            raise PluginInstallationRetirementOwnerError(
                "PLUGIN_LOCK_VERSION_CONFLICT")
        session.flush()

    def append_disabled_operation_history(self, transaction: object, *,
        installation_id: uuid.UUID, package_id: uuid.UUID, plugin_id: str,
        operation_id: str, actor_id: uuid.UUID, trace_id: uuid.UUID,
        audit_event_id: uuid.UUID) -> None:
        session = self._session(transaction)
        session.add(PluginEnabledOperationHistoryRow(
            plugin_installation_id=installation_id, plugin_package_id=package_id,
            plugin_id_normalized=plugin_id, operation_id=operation_id,
            transition="DISABLED", actor_id=actor_id, trace_id=trace_id,
            audit_event_id=audit_event_id))
        session.flush()

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginInstallationRetirementOwnerError(
                "PLUGIN_RETIREMENT_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session):
            raise PluginInstallationRetirementOwnerError(
                "PLUGIN_RETIREMENT_STORE_UNAVAILABLE")
        return session
