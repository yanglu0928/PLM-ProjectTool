"""PostgreSQL persistence for Plugin runtime revalidation."""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session
from plm_assistant.modules.plugin.application.installation_owner import InstallablePluginPackage
from plm_assistant.modules.plugin.application.revalidation_owner import (
    PluginRuntimeRevalidationContext, PluginRuntimeRevalidationOwnerError,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginEnabledOperationHistoryRow, PluginEnabledOperationRow, PluginInstallationRow,
    PluginPackageRow, PluginRuntimeValidationRow,
)

class SqlAlchemyPluginRuntimeRevalidationRepository:
    def identify_plugin(self, transaction: object, *, installation_id: uuid.UUID) -> str | None:
        return self._session(transaction).execute(
            select(PluginInstallationRow.plugin_id_normalized).where(
                PluginInstallationRow.plugin_installation_id == installation_id)
        ).scalar_one_or_none()

    def lock_plugin(self, transaction: object, *, plugin_id: str) -> None:
        key = f"plugin-activation:{plugin_id}"
        self._session(transaction).execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0)))
        )

    def load_context(self, transaction: object, *, installation_id: uuid.UUID) -> PluginRuntimeRevalidationContext | None:
        session = self._session(transaction)
        target = session.execute(
            select(PluginInstallationRow, PluginPackageRow.package_state,
                   PluginPackageRow.package_sha256, PluginPackageRow.manifest_snapshot)
            .join(PluginPackageRow,
                  (PluginPackageRow.plugin_package_id == PluginInstallationRow.plugin_package_id)
                  & (PluginPackageRow.plugin_id_normalized == PluginInstallationRow.plugin_id_normalized))
            .where(PluginInstallationRow.plugin_installation_id == installation_id)
            .with_for_update(of=[PluginInstallationRow, PluginPackageRow])
        ).first()
        if target is None:
            return None
        row, package_state, package_hash, manifest = target
        latest = session.execute(
            select(PluginRuntimeValidationRow)
            .where(PluginRuntimeValidationRow.plugin_installation_id == installation_id)
            .order_by(PluginRuntimeValidationRow.validated_at.desc(),
                      PluginRuntimeValidationRow.runtime_validation_id.desc())
            .limit(1).with_for_update()
        ).scalar_one_or_none()
        if latest is None:
            return None
        operations = tuple(session.execute(
            select(PluginEnabledOperationRow.operation_id)
            .where(PluginEnabledOperationRow.plugin_installation_id == installation_id)
            .order_by(PluginEnabledOperationRow.operation_id).with_for_update()
        ).scalars().all())
        package = InstallablePluginPackage(
            row.plugin_package_id,row.plugin_id_normalized,bytes(package_hash),dict(manifest))
        return PluginRuntimeRevalidationContext(
            row.plugin_id_normalized,row.plugin_installation_id,package,package_state,
            row.installation_state,row.lock_version,dict(row.validated_runtime_snapshot),
            latest.compatibility_state,dict(latest.runtime_snapshot),operations)

    def apply_revalidation(self, transaction: object, *,
                           context: PluginRuntimeRevalidationContext,
                           compatibility_state: str, runtime_snapshot: dict,
                           installation_state: str, actor_id: uuid.UUID,
                           changed_at: datetime) -> None:
        session = self._session(transaction)
        session.execute(text("SELECT set_config('plm.plugin_installation_owner_write','on',true)"))
        validation = PluginRuntimeValidationRow(
            plugin_installation_id=context.plugin_installation_id,
            compatibility_state=compatibility_state,runtime_snapshot=runtime_snapshot,
            validated_by=actor_id)
        session.add(validation)
        session.flush([validation])
        if compatibility_state == "INCOMPATIBLE" and context.enabled_operations:
            session.execute(delete(PluginEnabledOperationRow).where(
                PluginEnabledOperationRow.plugin_installation_id==context.plugin_installation_id))
        result = session.execute(
            update(PluginInstallationRow)
            .where(PluginInstallationRow.plugin_installation_id==context.plugin_installation_id,
                   PluginInstallationRow.lock_version==context.lock_version,
                   PluginInstallationRow.installation_state==context.installation_state)
            .values(installation_state=installation_state,
                    validated_runtime_snapshot=runtime_snapshot,updated_by=actor_id,
                    updated_at=changed_at,lock_version=context.lock_version+1)
        )
        if result.rowcount != 1:
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_LOCK_VERSION_CONFLICT")
        session.flush()

    def append_disabled_operation_history(self, transaction: object, *,
        installation_id: uuid.UUID, package_id: uuid.UUID, plugin_id: str,
        operation_id: str, actor_id: uuid.UUID, trace_id: uuid.UUID,
        audit_event_id: uuid.UUID) -> None:
        session=self._session(transaction)
        session.add(PluginEnabledOperationHistoryRow(
            plugin_installation_id=installation_id,plugin_package_id=package_id,
            plugin_id_normalized=plugin_id,operation_id=operation_id,
            transition="DISABLED",actor_id=actor_id,trace_id=trace_id,
            audit_event_id=audit_event_id))
        session.flush()

    @staticmethod
    def _session(transaction: object) -> Session:
        try: session=transaction.session
        except (AttributeError,RuntimeError):
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_STORE_UNAVAILABLE") from None
        if not isinstance(session,Session) or not session.in_transaction():
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_STORE_UNAVAILABLE")
        return session
