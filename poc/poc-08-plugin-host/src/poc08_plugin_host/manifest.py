from __future__ import annotations

import hashlib
import json
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PluginHostError


REQUIRED_FIELDS = {
    "id",
    "name",
    "version",
    "plugin_api_version",
    "supported_os",
    "supported_formats",
    "external_dependencies",
    "entry_point",
    "signature",
}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def current_os_key() -> str:
    architecture = platform.machine().lower()
    if architecture in {"amd64", "x86_64"}:
        architecture = "x86_64"
    family = "windows" if platform.system().lower() == "windows" else "debian"
    return f"{family}-{architecture}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    plugin_api_version: str
    supported_os: tuple[str, ...]
    supported_formats: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    entry_point: Path
    signature: str
    root: Path

    @classmethod
    def load(
        cls,
        plugin_dir: Path,
        *,
        supported_api_version: str,
        os_key: str | None = None,
    ) -> "PluginManifest":
        root = plugin_dir.resolve()
        manifest_path = root / "manifest.json"
        try:
            raw: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginHostError("PLUGIN_INVALID_MANIFEST", "Plugin manifest cannot be read") from exc

        missing = sorted(REQUIRED_FIELDS.difference(raw))
        if missing:
            raise PluginHostError("PLUGIN_INVALID_MANIFEST", "Plugin manifest is incomplete", detail=",".join(missing))
        if not all(isinstance(raw[field], str) and raw[field].strip() for field in ("id", "name", "version", "plugin_api_version", "entry_point", "signature")):
            raise PluginHostError("PLUGIN_INVALID_MANIFEST", "Plugin manifest contains invalid string fields")
        if not SEMVER.fullmatch(raw["version"]):
            raise PluginHostError("PLUGIN_INVALID_MANIFEST", "Plugin version must use semantic versioning")
        if raw["plugin_api_version"] != supported_api_version:
            raise PluginHostError("PLUGIN_INCOMPATIBLE_VERSION", "Plugin API version is not supported")
        for field in ("supported_os", "supported_formats", "external_dependencies"):
            if not isinstance(raw[field], list) or not all(isinstance(item, str) for item in raw[field]):
                raise PluginHostError("PLUGIN_INVALID_MANIFEST", f"{field} must be a string list")

        target_os = os_key or current_os_key()
        if target_os not in raw["supported_os"]:
            raise PluginHostError("PLUGIN_UNSUPPORTED_OS", "Plugin does not support the current operating system")

        entry_point = (root / raw["entry_point"]).resolve()
        if not entry_point.is_relative_to(root) or not entry_point.is_file():
            raise PluginHostError("PLUGIN_INVALID_ENTRY_POINT", "Plugin entry point is outside its package or missing")
        expected_signature = f"sha256:{file_sha256(entry_point)}"
        if raw["signature"].lower() != expected_signature:
            raise PluginHostError("PLUGIN_SIGNATURE_INVALID", "Plugin entry point integrity check failed")

        return cls(
            plugin_id=raw["id"],
            name=raw["name"],
            version=raw["version"],
            plugin_api_version=raw["plugin_api_version"],
            supported_os=tuple(raw["supported_os"]),
            supported_formats=tuple(raw["supported_formats"]),
            external_dependencies=tuple(raw["external_dependencies"]),
            entry_point=entry_point,
            signature=raw["signature"],
            root=root,
        )
