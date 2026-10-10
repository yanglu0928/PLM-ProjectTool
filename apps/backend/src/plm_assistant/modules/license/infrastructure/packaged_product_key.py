"""Fail-closed product-only Ed25519 trust anchor from the installed wheel."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from importlib import resources

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from plm_assistant.modules.license.application.license_validation import PRODUCT_CODE


PRODUCT_KEY_REF = "plm-project-tool-release-v1"
_RESOURCE = "trust/product_public_key.json"


class PackagedProductKeyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("product public key unavailable")


def _read_packaged_manifest() -> bytes:
    return (resources.files("plm_assistant.modules.license") / _RESOURCE).read_bytes()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PackagedProductKeyError()
        result[key] = value
    return result


class PackagedProductKey:
    """Both License key ports, with no runtime override or fallback source."""

    def __init__(self, *, read_manifest: Callable[[], bytes] = _read_packaged_manifest) -> None:
        try:
            raw = read_manifest()
            if type(raw) is not bytes or not 1 <= len(raw) <= 512:
                raise PackagedProductKeyError()
            value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs)
            if (type(value) is not dict
                    or set(value) != {"schema_version", "product_code", "key_ref", "public_key"}
                    or value["schema_version"] != "plm.product-public-key.v1"
                    or value["product_code"] != PRODUCT_CODE
                    or value["key_ref"] != PRODUCT_KEY_REF
                    or type(value["public_key"]) is not str):
                raise PackagedProductKeyError()
            key = base64.b64decode(value["public_key"], validate=True)
            if len(key) != 32 or base64.b64encode(key).decode("ascii") != value["public_key"]:
                raise PackagedProductKeyError()
            Ed25519PublicKey.from_public_bytes(key)
            self._key = key
        except Exception:
            raise PackagedProductKeyError() from None

    def product_key_ref(self) -> str:
        return PRODUCT_KEY_REF

    def resolve_public_key(self, public_key_ref: str) -> bytes | None:
        return self._key if type(public_key_ref) is str and public_key_ref == PRODUCT_KEY_REF else None
