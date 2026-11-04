"""Read-only PluginInstallation projection from one locked PostgreSQL snapshot."""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.plugin.application.installation_metadata import (
    PluginInstallationMetadataError,
    PluginInstallationMetadataView,
    PluginOperationMetadata,
)
from plm_assistant.modules.plugin.infrastructure.orm import (
    PluginEnabledOperationRow,
    PluginInstallationRow,
    PluginPackageRow,
    PluginManifestOperationRow,
    PluginRuntimeValidationRow,
)

_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()/-]{0,255}", re.ASCII)
_SAFE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+!_-]{0,63}", re.ASCII)


class SqlAlchemyPluginInstallationMetadataRepository:
    """Locks the installation row briefly so state/operations/runtime are one snapshot."""

    def get(
        self, transaction: object, *, installation_id: uuid.UUID,
    ) -> PluginInstallationMetadataView | None:
        session = self._session(transaction)
        pair = session.execute(
            select(PluginInstallationRow, PluginPackageRow)
            .join(
                PluginPackageRow,
                (PluginPackageRow.plugin_package_id == PluginInstallationRow.plugin_package_id)
                & (PluginPackageRow.plugin_id_normalized
                   == PluginInstallationRow.plugin_id_normalized),
            )
            .where(PluginInstallationRow.plugin_installation_id == installation_id)
            .with_for_update(of=PluginInstallationRow)
        ).first()
        if pair is None:
            return None
        installation, package = pair
        validation = session.execute(
            select(PluginRuntimeValidationRow)
            .where(
                PluginRuntimeValidationRow.plugin_installation_id
                == installation.plugin_installation_id,
            )
            .order_by(
                PluginRuntimeValidationRow.validated_at.desc(),
                PluginRuntimeValidationRow.runtime_validation_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if validation is None:
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        manifest = package.manifest_snapshot
        if type(manifest) is not dict:
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        name = manifest.get("name")
        api_version = manifest.get("plugin_api_version")
        supported_os = manifest.get("supported_os")
        architecture = manifest.get("architecture")
        if (type(name) is not str or _SAFE_NAME.fullmatch(name) is None
                or type(api_version) is not str or _SAFE_VERSION.fullmatch(api_version) is None
                or type(supported_os) is not list or not 1 <= len(supported_os) <= 3
                or any(item not in {"windows-11", "windows-server-2025", "debian-13"}
                       for item in supported_os)
                or type(architecture) is not str or architecture != "x86_64"):
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        operations_rows = session.execute(
            select(PluginManifestOperationRow)
            .where(PluginManifestOperationRow.plugin_package_id == package.plugin_package_id)
            .order_by(PluginManifestOperationRow.operation_id)
        ).scalars().all()
        operations: list[PluginOperationMetadata] = []
        for row in operations_rows:
            output_types = row.output_types
            if (type(row.operation_id) is not str or not row.operation_id.strip()
                    or type(output_types) is not list or not output_types
                    or any(type(item) is not str for item in output_types)):
                raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
            operations.append(PluginOperationMetadata(
                operation_id=row.operation_id,
                output_types=tuple(output_types),
                plugin_api_version=row.plugin_api_version,
            ))
        enabled = tuple(session.execute(
            select(PluginEnabledOperationRow.operation_id)
            .where(
                PluginEnabledOperationRow.plugin_installation_id
                == installation.plugin_installation_id,
            )
            .order_by(PluginEnabledOperationRow.operation_id)
        ).scalars().all())
        snapshot = validation.runtime_snapshot
        if type(snapshot) is not dict:
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        allowed = {"schema_version", "os", "architecture", "python_version",
                   "dependency_versions"}
        dependencies = snapshot.get("dependency_versions")
        if (set(snapshot) != allowed
                or snapshot.get("schema_version") != "1"
                or snapshot.get("os") not in {"windows-11", "windows-server-2025", "debian-13"}
                or snapshot.get("architecture") != "x86_64"
                or type(snapshot.get("python_version")) is not str
                or type(dependencies) is not dict or len(dependencies) > 256
                or any(type(k) is not str or type(v) is not str
                       or _SAFE_VERSION.fullmatch(k) is None
                       or _SAFE_VERSION.fullmatch(v) is None
                       for k, v in dependencies.items())):
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        digest = bytes(package.package_sha256)
        if (len(digest) != 32 or package.package_state not in {
                "VERIFIED", "REVOKED", "REJECTED", "IMPORTED"}):
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        return PluginInstallationMetadataView(
            plugin_installation_id=installation.plugin_installation_id,
            plugin_package_id=package.plugin_package_id,
            plugin_id=package.plugin_id_normalized,
            plugin_name=name,
            plugin_version=package.plugin_version,
            package_sha256=digest.hex(),
            package_state=package.package_state,
            plugin_api_version=api_version,
            supported_os=tuple(supported_os),
            architecture=architecture,
            operations=tuple(operations),
            installation_state=installation.installation_state,
            compatibility_state=validation.compatibility_state,
            runtime_snapshot={
                "schema_version": "1",
                "os": snapshot["os"],
                "architecture": snapshot["architecture"],
                "python_version": snapshot["python_version"],
                "dependency_versions": dict(sorted(dependencies.items())),
            },
            enabled_operations=enabled,
            lock_version=installation.lock_version,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise PluginInstallationMetadataError(
                "PLUGIN_INSTALLATION_UNAVAILABLE"
            ) from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        return session
