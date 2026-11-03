"""Bounded, read-only parser for versioned developer Plugin manifests."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


MAX_MANIFEST_BYTES = 65_536
MAX_MANIFEST_DEPTH = 16
MAX_MANIFEST_NODES = 4_096
MAX_OPERATIONS = 128
MAX_DEPENDENCIES = 256
_ALLOWED_OS = frozenset({"windows-11", "windows-server-2025", "debian-13"})
_ALLOWED_ARCHITECTURE = "x86_64"
_ROOT_KEYS = frozenset({
    "schema_version", "plugin_id", "name", "version", "plugin_api_version",
    "supported_os", "architecture", "entry_point", "operations", "dependencies",
})
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class PluginManifestError(ValueError):
    """Stable, non-sensitive failure code for invalid manifest input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PluginManifestOperation:
    operation_id: str
    output_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PluginManifestDependency:
    name: str
    version_spec: str
    kind: str


@dataclass(frozen=True, slots=True)
class ParsedPluginManifest:
    """Validated immutable declarations; they do not grant permission or trust."""

    plugin_id: str
    name: str
    version: str
    plugin_api_version: str
    supported_os: tuple[str, ...]
    architecture: str
    entry_point: str
    operations: tuple[PluginManifestOperation, ...]
    dependencies: tuple[PluginManifestDependency, ...]
    canonical_sha256: bytes = field(repr=False)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise PluginManifestError("PLUGIN_INVALID_MANIFEST")


def _check_json_tree(value: object, depth: int, count: list[int]) -> None:
    count[0] += 1
    if depth > MAX_MANIFEST_DEPTH or count[0] > MAX_MANIFEST_NODES:
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    if isinstance(value, dict):
        for key, child in value.items():
            if type(key) is not str:
                raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
            _check_json_tree(child, depth + 1, count)
    elif isinstance(value, list):
        for child in value:
            _check_json_tree(child, depth + 1, count)
    elif type(value) not in (str, int, bool, float) and value is not None:
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    elif type(value) is float:
        # The manifest V1 schema has no floating point fields.
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")


def _text(value: object, *, maximum: int, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    if len(value.encode("utf-8")) > maximum or value != value.strip():
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    return value


def _entry_point(value: object) -> str:
    if type(value) is not str or not value:
        raise PluginManifestError("PLUGIN_INVALID_ENTRY_POINT")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise PluginManifestError("PLUGIN_INVALID_ENTRY_POINT") from None
    if (
        len(encoded) > 512
        or value != value.strip()
        or any(unicodedata.category(char) == "Cc" for char in value)
    ):
        raise PluginManifestError("PLUGIN_INVALID_ENTRY_POINT")
    if "\\" in value or ":" in value or value.startswith("/"):
        raise PluginManifestError("PLUGIN_INVALID_ENTRY_POINT")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PluginManifestError("PLUGIN_INVALID_ENTRY_POINT")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise PluginManifestError("PLUGIN_INVALID_ENTRY_POINT")
    return value

def _string_list(value: object, *, maximum_items: int, item_maximum: int) -> tuple[str, ...]:
    if type(value) is not list or not 1 <= len(value) <= maximum_items:
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    items = tuple(_text(item, maximum=item_maximum) for item in value)
    if len(set(items)) != len(items):
        raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
    return items


class PluginManifestParser:
    """Parse only the bounded manifest bytes; never opens or executes a package."""

    def parse(self, manifest_bytes: bytes) -> ParsedPluginManifest:
        if (
            type(manifest_bytes) is not bytes
            or not 1 <= len(manifest_bytes) <= MAX_MANIFEST_BYTES
        ):
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        try:
            raw: Any = json.loads(
                manifest_bytes.decode("utf-8", "strict"),
                object_pairs_hook=_unique_pairs,
                parse_constant=_reject_constant,
            )
        except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST") from None
        # Give an invalid entry path its own stable error even if a later
        # generic structure check would otherwise reject another field first.
        parsed_entry_point: str | None = None
        if type(raw) is dict and "entry_point" in raw:
            parsed_entry_point = _entry_point(raw["entry_point"])
        if type(raw) is not dict or set(raw) != _ROOT_KEYS:
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        _check_json_tree(raw, 0, [0])

        if raw["schema_version"] != "plm.plugin.manifest.v1":
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        plugin_id = _text(raw["plugin_id"], maximum=128)
        if not _PLUGIN_ID.fullmatch(plugin_id):
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        name = _text(raw["name"], maximum=255)
        version = _text(raw["version"], maximum=64)
        api_version = _text(raw["plugin_api_version"], maximum=64)
        if not _SEMVER.fullmatch(version) or not _SEMVER.fullmatch(api_version):
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")

        supported_os = _string_list(raw["supported_os"], maximum_items=3, item_maximum=64)
        if any(os_name not in _ALLOWED_OS for os_name in supported_os):
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        architecture = _text(raw["architecture"], maximum=32)
        if architecture != _ALLOWED_ARCHITECTURE:
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        if parsed_entry_point is None:
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        entry_point = parsed_entry_point

        raw_operations = raw["operations"]
        if type(raw_operations) is not list or not 1 <= len(raw_operations) <= MAX_OPERATIONS:
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        operations: list[PluginManifestOperation] = []
        operation_ids: set[str] = set()
        for item in raw_operations:
            if type(item) is not dict or set(item) != {"operation_id", "output_types"}:
                raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
            operation_id = _text(item["operation_id"], maximum=255)
            if not _IDENTIFIER.fullmatch(operation_id) or operation_id in operation_ids:
                raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
            output_types = _string_list(item["output_types"], maximum_items=32, item_maximum=64)
            operation_ids.add(operation_id)
            operations.append(PluginManifestOperation(operation_id, output_types))

        raw_dependencies = raw["dependencies"]
        if type(raw_dependencies) is not list or len(raw_dependencies) > MAX_DEPENDENCIES:
            raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
        dependencies: list[PluginManifestDependency] = []
        dependency_ids: set[tuple[str, str]] = set()
        for item in raw_dependencies:
            if type(item) is not dict or set(item) != {"name", "version_spec", "kind"}:
                raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
            dependency_name = _text(item["name"], maximum=255)
            version_spec = _text(item["version_spec"], maximum=255)
            kind = _text(item["kind"], maximum=16)
            identity = (kind, dependency_name.casefold())
            if kind not in {"PYTHON", "OS", "SYSTEM"} or identity in dependency_ids:
                raise PluginManifestError("PLUGIN_INVALID_MANIFEST")
            dependency_ids.add(identity)
            dependencies.append(PluginManifestDependency(dependency_name, version_spec, kind))

        canonical = json.dumps(
            raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return ParsedPluginManifest(
            plugin_id=plugin_id,
            name=name,
            version=version,
            plugin_api_version=api_version,
            supported_os=supported_os,
            architecture=architecture,
            entry_point=entry_point,
            operations=tuple(operations),
            dependencies=tuple(dependencies),
            canonical_sha256=hashlib.sha256(canonical).digest(),
        )
