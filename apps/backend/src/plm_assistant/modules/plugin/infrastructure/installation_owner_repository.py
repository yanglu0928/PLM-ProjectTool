"""Transactional persistence for the controlled PluginInstallation Owner."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.installation_owner import (
    InstallablePluginPackage,
    PluginInstallationIdentity,
    PluginInstallationOwnerError,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginInstallationRow,
    PluginPackageRow,
    PluginRuntimeValidationRow,
)


class SqlAlchemyPluginInstallationRepository:
    """Uses only the caller's transaction and never commits it."""

    def lock_installation(self, transaction: object, *, installation_id: uuid.UUID) -> None:
        session = self._session(transaction)
        key = f"plugin-installation:{installation_id}"
        session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))

    def find_installation(
        self, transaction: object, *, installation_id: uuid.UUID,
    ) -> PluginInstallationIdentity | None:
        row = self._session(transaction).execute(
            select(PluginInstallationRow).where(
                PluginInstallationRow.plugin_installation_id == installation_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return None
        return PluginInstallationIdentity(
            plugin_installation_id=row.plugin_installation_id,
            plugin_package_id=row.plugin_package_id,
            plugin_id_normalized=row.plugin_id_normalized,
            installed_by=row.installed_by,
            installation_state=row.installation_state,
            validated_runtime_snapshot=dict(row.validated_runtime_snapshot),
        )

    def find_verified_package(
        self, transaction: object, *, package_id: uuid.UUID,
    ) -> InstallablePluginPackage | None:
        row = self._session(transaction).execute(
            select(PluginPackageRow).where(
                PluginPackageRow.plugin_package_id == package_id,
                PluginPackageRow.package_state == "VERIFIED",
            ).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return None
        return InstallablePluginPackage(
            plugin_package_id=row.plugin_package_id,
            plugin_id_normalized=row.plugin_id_normalized,
            package_sha256=bytes(row.package_sha256),
            manifest_snapshot=dict(row.manifest_snapshot),
        )

    def authorize_owner_inserts(self, transaction: object) -> None:
        self._session(transaction).execute(
            text("SELECT set_config('plm.plugin_installation_owner_write', 'on', true)")
        )

    def create_installed(
        self, transaction: object, *, installation_id: uuid.UUID,
        package: InstallablePluginPackage, actor_id: uuid.UUID,
        runtime_snapshot: dict,
    ) -> PluginInstallationIdentity:
        session = self._session(transaction)
        row = PluginInstallationRow(
            plugin_installation_id=installation_id,
            plugin_package_id=package.plugin_package_id,
            plugin_id_normalized=package.plugin_id_normalized,
            installation_state="INSTALLED",
            validated_runtime_snapshot=runtime_snapshot,
            installed_by=actor_id,
            created_by=actor_id,
            updated_by=actor_id,
            lock_version=0,
        )
        session.add(row)
        session.flush([row])
        return PluginInstallationIdentity(
            plugin_installation_id=installation_id,
            plugin_package_id=package.plugin_package_id,
            plugin_id_normalized=package.plugin_id_normalized,
            installed_by=actor_id,
            installation_state="INSTALLED",
            validated_runtime_snapshot=dict(runtime_snapshot),
        )

    def append_runtime_validation(
        self, transaction: object, *, installation_id: uuid.UUID,
        actor_id: uuid.UUID, runtime_snapshot: dict,
    ) -> None:
        session = self._session(transaction)
        session.add(PluginRuntimeValidationRow(
            plugin_installation_id=installation_id,
            compatibility_state="COMPATIBLE",
            runtime_snapshot=runtime_snapshot,
            validated_by=actor_id,
        ))
        session.flush()

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginInstallationOwnerError(
                "PLUGIN_INSTALLATION_STORE_UNAVAILABLE"
            ) from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginInstallationOwnerError(
                "PLUGIN_INSTALLATION_STORE_UNAVAILABLE"
            )
        return session
