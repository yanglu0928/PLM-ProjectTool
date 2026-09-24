from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import PluginHostError
from .host import InvocationResult, PluginHost
from .manifest import PluginManifest


class PluginRegistry:
    def __init__(self, *, supported_api_version: str = "1.0", os_key: str | None = None) -> None:
        self.supported_api_version = supported_api_version
        self.os_key = os_key
        self._active: dict[str, PluginManifest] = {}
        self._enabled: dict[str, bool] = {}

    def activate(self, plugin_dir: Path) -> PluginManifest:
        manifest = PluginManifest.load(
            plugin_dir,
            supported_api_version=self.supported_api_version,
            os_key=self.os_key,
        )
        self._active[manifest.plugin_id] = manifest
        self._enabled.setdefault(manifest.plugin_id, True)
        return manifest

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        if plugin_id not in self._active:
            raise PluginHostError("PLUGIN_NOT_FOUND", "Plugin is not installed")
        self._enabled[plugin_id] = enabled

    def require_active(self, plugin_id: str) -> PluginManifest:
        manifest = self._active.get(plugin_id)
        if manifest is None:
            raise PluginHostError("PLUGIN_NOT_FOUND", "Plugin is not installed")
        if not self._enabled.get(plugin_id, False):
            raise PluginHostError("PLUGIN_DISABLED", "Plugin is disabled")
        return manifest


class PluginService:
    def __init__(self, registry: PluginRegistry, host: PluginHost) -> None:
        self.registry = registry
        self.host = host

    def invoke(
        self,
        plugin_id: str,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_seconds: float = 2.0,
    ) -> InvocationResult:
        manifest = self.registry.require_active(plugin_id)
        return self.host.invoke(manifest, method, params, timeout_seconds=timeout_seconds)
