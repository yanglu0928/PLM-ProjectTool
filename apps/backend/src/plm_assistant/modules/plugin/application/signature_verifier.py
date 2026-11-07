"""Ed25519 verification boundary for developer-signed Plugin packages.

This proves cryptographic authenticity of exact archive bytes only. It does not
validate a manifest, compatibility, installability, or executable safety.
"""
from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


_SIGNATURE_DOMAIN = b"PLM-PLUGIN-PACKAGE\x00v1\x00"
_MIN_KEY_REF_BYTES = 1
_MAX_KEY_REF_BYTES = 512
_PACKAGE_HASH_BYTES = 32
_ED25519_PUBLIC_KEY_BYTES = 32
_ED25519_SIGNATURE_BYTES = 64


class PluginSignatureVerificationError(ValueError):
    """Non-sensitive, stable failure code for a rejected package signature."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TrustedPluginSigner:
    """A signer resolved from a trusted source; public key bytes are never repr'd."""

    signer_key_ref: str
    public_key_raw: bytes = field(repr=False)
    state: str = "ACTIVE"


class TrustedPluginSignerResolver(Protocol):
    def resolve_trusted_signer(self, signer_key_ref: str) -> TrustedPluginSigner | None:
        """Return an externally trusted signer; package-supplied keys are not accepted."""


@dataclass(frozen=True, slots=True)
class PluginPackageSignatureVerification:
    """Cryptographic provenance only; this is not package or code safety approval."""

    signer_key_ref: str
    package_sha256: bytes
    algorithm: str = "Ed25519"


def _key_ref_bytes(value: object) -> bytes:
    if type(value) is not str or not value or value != value.strip():
        raise PluginSignatureVerificationError("PLUGIN_PACKAGE_INVALID")
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise PluginSignatureVerificationError("PLUGIN_PACKAGE_INVALID")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise PluginSignatureVerificationError("PLUGIN_PACKAGE_INVALID") from None
    if not _MIN_KEY_REF_BYTES <= len(encoded) <= _MAX_KEY_REF_BYTES:
        raise PluginSignatureVerificationError("PLUGIN_PACKAGE_INVALID")
    return encoded


def _signature_message(signer_key_ref: str, package_sha256: bytes) -> bytes:
    key_ref = _key_ref_bytes(signer_key_ref)
    if type(package_sha256) is not bytes or len(package_sha256) != _PACKAGE_HASH_BYTES:
        raise PluginSignatureVerificationError("PLUGIN_PACKAGE_INVALID")
    # A 2-byte length prefix makes the key reference unambiguous in the message.
    return (
        _SIGNATURE_DOMAIN
        + len(key_ref).to_bytes(2, byteorder="big", signed=False)
        + key_ref
        + package_sha256
    )


class PluginPackageSignatureVerifier:
    """Verify detached package signatures against externally resolved trust."""

    def __init__(self, signer_resolver: TrustedPluginSignerResolver) -> None:
        if signer_resolver is None:
            raise ValueError("trusted plugin signer resolver is required")
        self._signer_resolver = signer_resolver

    def verify(
        self,
        package_bytes: bytes,
        *,
        signature: bytes,
        signer_key_ref: str,
    ) -> PluginPackageSignatureVerification:
        if type(package_bytes) is not bytes or not package_bytes:
            raise PluginSignatureVerificationError("PLUGIN_PACKAGE_INVALID")
        if type(signature) is not bytes or len(signature) != _ED25519_SIGNATURE_BYTES:
            raise PluginSignatureVerificationError("PLUGIN_SIGNATURE_INVALID")

        message_key_ref = _key_ref_bytes(signer_key_ref)
        del message_key_ref  # Validate before calling the trust resolver.
        try:
            signer = self._signer_resolver.resolve_trusted_signer(signer_key_ref)
        except Exception:
            raise PluginSignatureVerificationError("PLUGIN_SIGNER_UNTRUSTED") from None
        if (
            not isinstance(signer, TrustedPluginSigner)
            or signer.signer_key_ref != signer_key_ref
            or signer.state != "ACTIVE"
            or type(signer.public_key_raw) is not bytes
            or len(signer.public_key_raw) != _ED25519_PUBLIC_KEY_BYTES
        ):
            raise PluginSignatureVerificationError("PLUGIN_SIGNER_UNTRUSTED")

        package_sha256 = hashlib.sha256(package_bytes).digest()
        signed_message = _signature_message(signer_key_ref, package_sha256)
        try:
            Ed25519PublicKey.from_public_bytes(signer.public_key_raw).verify(signature, signed_message)
        except (InvalidSignature, ValueError):
            raise PluginSignatureVerificationError("PLUGIN_SIGNATURE_INVALID") from None
        return PluginPackageSignatureVerification(
            signer_key_ref=signer_key_ref,
            package_sha256=package_sha256,
        )
