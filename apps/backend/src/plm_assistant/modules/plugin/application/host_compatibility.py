"""Static, versioned compatibility policy for the supported product targets."""
from __future__ import annotations

from plm_assistant.modules.plugin.application.manifest_parser import ParsedPluginManifest
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageCompatibilityAssessment,
)

_POLICY_REF = "host.platforms.v1"
_SUPPORTED_OS = frozenset({"windows-11", "windows-server-2025", "debian-13"})
_PLUGIN_API_MAJOR = "1"


class HostPlatformsPluginCompatibility:
    """Check only declared host/API compatibility; this is not execution approval."""

    def evaluate(
        self, manifest: ParsedPluginManifest, *, policy_ref: str,
    ) -> PluginPackageCompatibilityAssessment:
        if policy_ref != _POLICY_REF or type(manifest) is not ParsedPluginManifest:
            return PluginPackageCompatibilityAssessment(
                False, "PLUGIN_PACKAGE_POLICY_UNAVAILABLE",
            )
        if manifest.plugin_api_version.split(".", 1)[0] != _PLUGIN_API_MAJOR:
            return PluginPackageCompatibilityAssessment(
                False, "PLUGIN_API_INCOMPATIBLE",
            )
        if (manifest.architecture != "x86_64"
                or not set(manifest.supported_os).intersection(_SUPPORTED_OS)):
            return PluginPackageCompatibilityAssessment(
                False, "PLUGIN_OS_INCOMPATIBLE",
            )
        return PluginPackageCompatibilityAssessment(True)
