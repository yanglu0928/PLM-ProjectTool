"""PostgreSQL repository for atomic Plugin operation activation."""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session
from plm_assistant.modules.plugin.application.activation_owner import (
    PluginActivationContext, PluginActivationOwnerError, PluginOperationTransition,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginEnabledOperationHistoryRow, PluginEnabledOperationRow,
    PluginInstallationRow, PluginManifestOperationRow, PluginPackageRow,
    PluginRuntimeValidationRow,
)

class SqlAlchemyPluginActivationRepository:
    def identify_plugin(self, transaction: object, *, installation_id: uuid.UUID) -> str | None:
        return self._session(transaction).execute(
            select(PluginInstallationRow.plugin_id_normalized).where(
                PluginInstallationRow.plugin_installation_id == installation_id
            )
        ).scalar_one_or_none()

    def lock_plugin(self, transaction: object, *, plugin_id: str) -> None:
        key = f"plugin-activation:{plugin_id}"
        self._session(transaction).execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0)))
        )

    def load_activation_context(self, transaction: object, *,
                                installation_id: uuid.UUID) -> PluginActivationContext | None:
        session = self._session(transaction)
        target = session.execute(
            select(PluginInstallationRow, PluginPackageRow.package_state)
            .join(PluginPackageRow,
                  (PluginPackageRow.plugin_package_id == PluginInstallationRow.plugin_package_id)
                  & (PluginPackageRow.plugin_id_normalized == PluginInstallationRow.plugin_id_normalized))
            .where(PluginInstallationRow.plugin_installation_id == installation_id)
            .with_for_update(of=[PluginInstallationRow, PluginPackageRow])
        ).first()
        if target is None:
            return None
        target_row, package_state = target
        rows = session.execute(
            select(PluginInstallationRow)
            .where(PluginInstallationRow.plugin_id_normalized == target_row.plugin_id_normalized)
            .order_by(PluginInstallationRow.plugin_installation_id)
            .with_for_update()
        ).scalars().all()
        states = {row.plugin_installation_id: row.installation_state for row in rows}
        versions = {row.plugin_installation_id: row.lock_version for row in rows}
        packages = {row.plugin_installation_id: row.plugin_package_id for row in rows}
        enabled: dict[uuid.UUID, set[str]] = {row.plugin_installation_id: set() for row in rows}
        pairs = session.execute(
            select(PluginEnabledOperationRow.plugin_installation_id,
                   PluginEnabledOperationRow.operation_id)
            .where(PluginEnabledOperationRow.plugin_id_normalized == target_row.plugin_id_normalized)
            .order_by(PluginEnabledOperationRow.plugin_installation_id,
                      PluginEnabledOperationRow.operation_id)
            .with_for_update()
        ).all()
        for install_id, operation_id in pairs:
            enabled[install_id].add(operation_id)
        declared = frozenset(session.execute(
            select(PluginManifestOperationRow.operation_id)
            .where(PluginManifestOperationRow.plugin_package_id == target_row.plugin_package_id)
        ).scalars().all())
        latest = session.execute(
            select(PluginRuntimeValidationRow)
            .where(PluginRuntimeValidationRow.plugin_installation_id == installation_id)
            .order_by(PluginRuntimeValidationRow.validated_at.desc(),
                      PluginRuntimeValidationRow.runtime_validation_id.desc())
            .limit(1).with_for_update()
        ).scalar_one_or_none()
        return PluginActivationContext(
            plugin_id_normalized=target_row.plugin_id_normalized,
            target_installation_id=target_row.plugin_installation_id,
            target_package_id=target_row.plugin_package_id,
            target_package_state=package_state,
            target_state=target_row.installation_state,
            target_lock_version=target_row.lock_version,
            target_runtime_snapshot=dict(target_row.validated_runtime_snapshot),
            latest_validation_state=latest.compatibility_state if latest else None,
            latest_runtime_snapshot=dict(latest.runtime_snapshot) if latest else {},
            declared_operations=declared, installation_states=states,
            installation_lock_versions=versions, package_ids=packages,
            enabled_operations={key: frozenset(value) for key, value in enabled.items()},
        )

    def authorize_owner_writes(self, transaction: object) -> None:
        self._session(transaction).execute(
            text("SELECT set_config('plm.plugin_installation_owner_write','on',true)")
        )

    def apply_activation(self, transaction: object, *, context: PluginActivationContext,
                         desired_operations: frozenset[str],
                         new_states: dict[uuid.UUID, str], actor_id: uuid.UUID,
                         changed_at: datetime) -> None:
        session = self._session(transaction)
        target = context.target_installation_id
        prior_owners = [item for item, operations in context.enabled_operations.items()
                        if item != target and operations.intersection(desired_operations)]
        for item in [target, *sorted(prior_owners, key=str)]:
            operations = context.enabled_operations.get(item, frozenset())
            removed = operations if item == target else operations.intersection(desired_operations)
            if removed:
                session.execute(delete(PluginEnabledOperationRow).where(
                    PluginEnabledOperationRow.plugin_installation_id == item,
                    PluginEnabledOperationRow.operation_id.in_(tuple(removed)),
                ))
        for operation_id in sorted(desired_operations):
            session.add(PluginEnabledOperationRow(
                plugin_installation_id=target, operation_id=operation_id,
                plugin_package_id=context.target_package_id,
                plugin_id_normalized=context.plugin_id_normalized,
            ))
        for item, next_state in new_states.items():
            prior_state = context.installation_states[item]
            expected = context.installation_lock_versions[item]
            values = {"installation_state": next_state, "updated_by": actor_id,
                      "updated_at": changed_at, "lock_version": expected + 1}
            if next_state == "ENABLED":
                values["enabled_by"] = actor_id
                values["enabled_at"] = changed_at
            result = session.execute(
                update(PluginInstallationRow)
                .where(PluginInstallationRow.plugin_installation_id == item,
                       PluginInstallationRow.lock_version == expected,
                       PluginInstallationRow.installation_state == prior_state)
                .values(**values)
            )
            if result.rowcount != 1:
                raise PluginActivationOwnerError("PLUGIN_LOCK_VERSION_CONFLICT")
        session.flush()

    def append_operation_history(self, transaction: object, *,
                                 transition: PluginOperationTransition,
                                 actor_id: uuid.UUID, trace_id: uuid.UUID,
                                 audit_event_id: uuid.UUID) -> None:
        session = self._session(transaction)
        plugin_id = session.execute(
            select(PluginInstallationRow.plugin_id_normalized).where(
                PluginInstallationRow.plugin_installation_id == transition.installation_id)
        ).scalar_one_or_none()
        if type(plugin_id) is not str:
            raise PluginActivationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
        session.add(PluginEnabledOperationHistoryRow(
            plugin_installation_id=transition.installation_id,
            plugin_package_id=transition.package_id,
            plugin_id_normalized=plugin_id, operation_id=transition.operation_id,
            transition=transition.transition, actor_id=actor_id, trace_id=trace_id,
            audit_event_id=audit_event_id,
        ))
        session.flush()

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STORE_UNAVAILABLE")
        return session
