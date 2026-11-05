"""Read-only verification of a registered Plugin archive; never installs or executes."""
from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.plugin.application.package_archive_inspector import (
    InspectedPluginPackage, PluginPackageArchiveInspector,
)
from plm_assistant.modules.plugin.application.installation_owner import (
    PluginPackageArchiveProof,
)
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageIdentity, PluginPackageRegistrationService,
)


class LocalPluginPackageArchiveEvidence:
    def __init__(self, *, storage: LocalFileStorage,
                 inspector: PluginPackageArchiveInspector) -> None:
        if storage is None or inspector is None:
            raise ValueError("Package archive evidence dependencies are required")
        self._storage = storage
        self._inspector = inspector

    def inspect_registered_package(
        self, package: PluginPackageIdentity,
    ) -> PluginPackageArchiveProof | None:
        if (type(package) is not PluginPackageIdentity
                or package.package_state != "VERIFIED"
                or type(package.plugin_package_id) is not uuid.UUID
                or type(package.package_sha256) is not bytes
                or len(package.package_sha256) != 32
                or type(package.signature) is not bytes
                or type(package.signer_key_ref) is not str):
            return None
        try:
            body = self._storage.load_verified_plugin_package_archive(
                package_id=package.plugin_package_id, expected_sha256=package.package_sha256)
            inspected = self._inspector.inspect_and_verify(
                body, detached_signature=package.signature,
                signer_key_ref=package.signer_key_ref)
            if (type(inspected) is not InspectedPluginPackage
                    or not hmac.compare_digest(
                        inspected.signature_verification.package_sha256,
                        package.package_sha256)
                    or inspected.signature_verification.signer_key_ref != package.signer_key_ref
                    or PluginPackageRegistrationService._manifest_snapshot(
                        inspected.manifest) != package.manifest_snapshot
                    or inspected.manifest.plugin_id != package.plugin_id_normalized
                    or inspected.manifest.version != package.plugin_version):
                return None
        except Exception:
            return None
        return PluginPackageArchiveProof(
            plugin_package_id=package.plugin_package_id,
            plugin_id_normalized=package.plugin_id_normalized,
            plugin_version=package.plugin_version,
            package_sha256=bytes(package.package_sha256),
            present_and_verified=True)
