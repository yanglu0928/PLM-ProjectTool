"""Append-only PostgreSQL snapshots for Plugin disable HTTP replay."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.activation_owner import (
    DisablePluginInstallationCommand, PluginActivationResult,
)
from plm_assistant.modules.plugin.application.installation_disable import (
    PluginInstallationDisableError, PluginInstallationDisableResult,
)
from plm_assistant.modules.plugin.infrastructure.orm import PluginInstallationDisableResultRow


class SqlAlchemyPluginDisableResultRepository:
    def record(self, transaction: object, *,
               command: DisablePluginInstallationCommand,
               result: PluginActivationResult) -> PluginInstallationDisableResult:
        session = self._session(transaction)
        if (type(command) is not DisablePluginInstallationCommand
                or type(result) is not PluginActivationResult
                or result.plugin_installation_id != command.plugin_installation_id
                or result.installation_state != "DISABLED"
                or result.lock_version not in (
                    command.expected_lock_version,
                    command.expected_lock_version + 1,
                )
                or result.changed != (result.lock_version == command.expected_lock_version + 1)):
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
        result_id = uuid.uuid4()
        session.execute(text(
            "SELECT set_config('plm.plugin_installation_owner_write','on',true)"
        ))
        session.add(PluginInstallationDisableResultRow(
            disable_result_id=result_id,
            plugin_installation_id=command.plugin_installation_id,
            actor_id=command.actor_id,
            trace_id=command.trace_id,
            expected_lock_version=command.expected_lock_version,
            result_lock_version=result.lock_version,
            installation_state="DISABLED",
            changed=result.changed,
        ))
        session.flush()
        row = session.execute(
            select(PluginInstallationDisableResultRow).where(
                PluginInstallationDisableResultRow.disable_result_id == result_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
        return self._view(row)

    def get(self, transaction: object, *,
            result_id: uuid.UUID) -> PluginInstallationDisableResult | None:
        if type(result_id) is not uuid.UUID or result_id.int == 0:
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
        row = self._session(transaction).execute(
            select(PluginInstallationDisableResultRow).where(
                PluginInstallationDisableResultRow.disable_result_id == result_id,
            )
        ).scalar_one_or_none()
        return None if row is None else self._view(row)

    @staticmethod
    def _view(row: PluginInstallationDisableResultRow) -> PluginInstallationDisableResult:
        result = PluginInstallationDisableResult(
            result_id=row.disable_result_id,
            plugin_installation_id=row.plugin_installation_id,
            actor_id=row.actor_id,
            trace_id=row.trace_id,
            expected_lock_version=row.expected_lock_version,
            result_lock_version=row.result_lock_version,
            installation_state=row.installation_state,
            changed=row.changed,
            created_at=row.created_at,
        )
        if (result.installation_state != "DISABLED"
                or result.result_lock_version not in (
                    result.expected_lock_version,
                    result.expected_lock_version + 1,
                )
                or result.changed != (
                    result.result_lock_version == result.expected_lock_version + 1
                )
                or result.created_at.tzinfo is None):
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
        return result

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
        return session
