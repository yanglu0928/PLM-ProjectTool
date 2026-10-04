"""Ed25519 authenticity preflight; this does not determine License validity."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass, field
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


MAX_DOCUMENT_BYTES = 65_536
MAX_PAYLOAD_DEPTH = 16
MAX_PAYLOAD_NODES = 1_024


class LicenseSignatureError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PublicKeyResolverPort(Protocol):
    def resolve_public_key(self, public_key_ref: str) -> bytes | None:
        """Return only a trusted configured Ed25519 public key, never request-supplied key material."""


@dataclass(frozen=True, slots=True)
class SignatureVerifiedDocument:
    """Cryptographic authenticity only; NOT a VALID License or entitlement."""

    public_key_ref: str
    document_sha256: bytes = field(repr=False)
    canonical_payload: bytes = field(repr=False)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")


def _check_payload(value: object, depth: int, counter: list[int]) -> None:
    counter[0] += 1
    if depth > MAX_PAYLOAD_DEPTH or counter[0] > MAX_PAYLOAD_NODES:
        raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")
            _check_payload(item, depth + 1, counter)
    elif isinstance(value, list):
        for item in value:
            _check_payload(item, depth + 1, counter)
    elif type(value) not in (str, int, bool):
        raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")


class LicenseSignatureVerifier:
    def __init__(self, key_resolver: PublicKeyResolverPort) -> None:
        if key_resolver is None:
            raise ValueError("trusted public key resolver is required")
        self._key_resolver = key_resolver

    def verify(self, signed_document: bytes, *, public_key_ref: str) -> SignatureVerifiedDocument:
        if type(signed_document) is not bytes or not 1 <= len(signed_document) <= MAX_DOCUMENT_BYTES:
            raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")
        if type(public_key_ref) is not str or not 1 <= len(public_key_ref) <= 128:
            raise LicenseSignatureError("LICENSE_PUBLIC_KEY_INVALID")
        try:
            raw = json.loads(signed_document.decode("utf-8", "strict"),
                             object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
            raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID") from None
        if (type(raw) is not dict or set(raw) != {"algorithm", "payload", "signature"}
                or raw["algorithm"] != "Ed25519" or type(raw["payload"]) is not dict
                or type(raw["signature"]) is not str):
            raise LicenseSignatureError("LICENSE_DOCUMENT_INVALID")
        _check_payload(raw["payload"], 0, [0])
        try:
            signature = base64.b64decode(raw["signature"], validate=True)
        except (ValueError, binascii.Error):
            raise LicenseSignatureError("LICENSE_SIGNATURE_INVALID") from None
        if len(signature) != 64:
            raise LicenseSignatureError("LICENSE_SIGNATURE_INVALID")
        key = self._key_resolver.resolve_public_key(public_key_ref)
        if type(key) is not bytes or len(key) != 32:
            raise LicenseSignatureError("LICENSE_PUBLIC_KEY_INVALID")
        canonical = json.dumps(raw["payload"], ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(signature, canonical)
        except (InvalidSignature, ValueError):
            raise LicenseSignatureError("LICENSE_SIGNATURE_INVALID") from None
        return SignatureVerifiedDocument(public_key_ref, hashlib.sha256(signed_document).digest(), canonical)
