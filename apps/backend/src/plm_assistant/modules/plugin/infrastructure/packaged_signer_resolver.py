"""Read-only resolver for the versioned publisher key manifest shipped with the backend."""
from __future__ import annotations

import base64
import json
import unicodedata
from importlib import resources

from plm_assistant.modules.plugin.application.signature_verifier import (
    TrustedPluginSigner,
)


_MANIFEST_NAME = "developer_keys.json"
_SCHEMA_VERSION = "plm.plugin.publisher-keys.v1"
_MAX_MANIFEST_BYTES = 65_536
_MAX_KEYS = 128
_MAX_KEY_REF_BYTES = 512
_PUBLIC_KEY_BYTES = 32


class PluginTrustConfigurationError(RuntimeError):
    """Sanitized failure for an invalid or unavailable packaged trust manifest."""

    def __init__(self) -> None:
        super().__init__("plugin signer trust configuration unavailable")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise PluginTrustConfigurationError()
        value[key] = item
    return value


def _valid_key_ref(value: object) -> bool:
    if type(value) is not str or not value or value != value.strip():
        return False
    if any(unicodedata.category(char) == "Cc" for char in value):
        return False
    try:
        size = len(value.encode("utf-8", "strict"))
    except UnicodeError:
        return False
    return 1 <= size <= _MAX_KEY_REF_BYTES


def _reject_constant(_value: str) -> object:
    raise PluginTrustConfigurationError()


def _load_packaged_manifest() -> bytes:
    return (
        resources.files("plm_assistant.modules.plugin")
        .joinpath("trust")
        .joinpath(_MANIFEST_NAME)
        .read_bytes()
    )


def _parse_manifest(manifest_bytes: bytes) -> dict[str, TrustedPluginSigner]:
    if (
        type(manifest_bytes) is not bytes
        or not 1 <= len(manifest_bytes) <= _MAX_MANIFEST_BYTES
    ):
        raise PluginTrustConfigurationError()
    try:
        value = json.loads(
            manifest_bytes.decode("utf-8", "strict"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except Exception:
        raise PluginTrustConfigurationError() from None

    if (
        type(value) is not dict
        or set(value) != {"schema_version", "keys"}
        or value["schema_version"] != _SCHEMA_VERSION
        or type(value["keys"]) is not list
        or len(value["keys"]) > _MAX_KEYS
    ):
        raise PluginTrustConfigurationError()

    seen: set[str] = set()
    active: dict[str, TrustedPluginSigner] = {}
    for item in value["keys"]:
        if (
            type(item) is not dict
            or set(item) != {"key_ref", "algorithm", "public_key", "state"}
            or not _valid_key_ref(item["key_ref"])
            or item["key_ref"] in seen
            or item["algorithm"] != "Ed25519"
            or item["state"] not in {"ACTIVE", "REVOKED"}
            or type(item["public_key"]) is not str
        ):
            raise PluginTrustConfigurationError()
        try:
            public_key = base64.b64decode(item["public_key"], validate=True)
        except Exception:
            raise PluginTrustConfigurationError() from None
        if (
            len(public_key) != _PUBLIC_KEY_BYTES
            or base64.b64encode(public_key).decode("ascii") != item["public_key"]
        ):
            raise PluginTrustConfigurationError()
        key_ref = item["key_ref"]
        seen.add(key_ref)
        if item["state"] == "ACTIVE":
            active[key_ref] = TrustedPluginSigner(
                signer_key_ref=key_ref,
                public_key_raw=public_key,
                state="ACTIVE",
            )
    return active


class PackagedPluginSignerResolver:
    """Resolve only ACTIVE signer records from the shipped, read-only key manifest."""

    def __init__(self) -> None:
        try:
            self._active_signers = _parse_manifest(_load_packaged_manifest())
        except PluginTrustConfigurationError:
            raise
        except Exception:
            raise PluginTrustConfigurationError() from None

    def resolve_trusted_signer(self, signer_key_ref: str) -> TrustedPluginSigner | None:
        if not _valid_key_ref(signer_key_ref):
            return None
        return self._active_signers.get(signer_key_ref)
