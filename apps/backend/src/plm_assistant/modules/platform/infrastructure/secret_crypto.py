"""Versioned AES-GCM Secret cipher; deployment key source is injected externally."""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass, field
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef,
)


ALGORITHM = "AES-256-GCM-V1"
_MAX_PLAINTEXT = 65520  # PostgreSQL cipher limit 65536 minus 16-byte GCM tag.


class SecretCryptoError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("secret unavailable")


class SecretKeyProviderPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class EncryptedSecretDraft:
    encrypted_payload: bytes = field(repr=False)
    encryption_metadata: bytes = field(repr=False)
    key_provider_ref: str = field(repr=False)


def _aad(secret_ref: SecretRef, purpose: SecretPurpose,
         consumer: SecretConsumer, version_no: int, key_ref: str) -> bytes:
    if (not isinstance(secret_ref, SecretRef)
            or not isinstance(purpose, SecretPurpose)
            or not isinstance(consumer, SecretConsumer)
            or type(version_no) is not int or version_no < 1
            or type(key_ref) is not str or not 1 <= len(key_ref) <= 128):
        raise SecretCryptoError()
    return json.dumps({
        "domain": "plm-secret-v1", "secret_id": str(secret_ref.secret_id),
        "purpose": purpose.value, "consumer": consumer.value,
        "version_no": version_no, "key_ref": key_ref,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class AesGcmSecretCrypto:
    def __init__(self, provider: SecretKeyProviderPort, *, key_ref: str) -> None:
        if provider is None or type(key_ref) is not str or not 1 <= len(key_ref) <= 128:
            raise ValueError("trusted Secret key provider and reference are required")
        self._provider, self._key_ref = provider, key_ref

    def encrypt(self, *, secret_ref: SecretRef, purpose: SecretPurpose,
                consumer: SecretConsumer, version_no: int,
                plaintext: bytearray) -> EncryptedSecretDraft:
        try:
            if type(plaintext) is not bytearray or not 1 <= len(plaintext) <= _MAX_PLAINTEXT:
                raise SecretCryptoError()
            aad = _aad(secret_ref, purpose, consumer, version_no, self._key_ref)
            key = self._key(self._key_ref)
            nonce = secrets.token_bytes(12)
            try:
                ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
            finally:
                key[:] = b"\x00" * len(key)
            metadata = json.dumps({
                "algorithm": ALGORITHM,
                "nonce": base64.b64encode(nonce).decode("ascii"),
            }, sort_keys=True, separators=(",", ":")).encode("ascii")
            return EncryptedSecretDraft(ciphertext, metadata, self._key_ref)
        except Exception:
            raise SecretCryptoError() from None
        finally:
            if type(plaintext) is bytearray:
                plaintext[:] = b"\x00" * len(plaintext)

    def decrypt(self, envelope: SecretEnvelope) -> bytearray:
        try:
            if (not isinstance(envelope, SecretEnvelope)
                    or type(envelope.encrypted_payload) is not bytes
                    or not 17 <= len(envelope.encrypted_payload) <= 65536
                    or type(envelope.encryption_metadata) is not bytes
                    or len(envelope.encryption_metadata) > 512):
                raise SecretCryptoError()
            metadata = json.loads(envelope.encryption_metadata)
            if (type(metadata) is not dict or set(metadata) != {"algorithm", "nonce"}
                    or metadata["algorithm"] != ALGORITHM
                    or type(metadata["nonce"]) is not str):
                raise SecretCryptoError()
            nonce = base64.b64decode(metadata["nonce"], validate=True)
            if len(nonce) != 12 or base64.b64encode(nonce).decode("ascii") != metadata["nonce"]:
                raise SecretCryptoError()
            aad = _aad(envelope.secret_ref, envelope.purpose,
                       envelope.allowed_consumer, envelope.version_no,
                       envelope.key_provider_ref)
            key = self._key(envelope.key_provider_ref)
            buffer = bytearray(len(envelope.encrypted_payload) - 16)
            try:
                AESGCM(key).decrypt_into(nonce, envelope.encrypted_payload, aad, buffer)
                return buffer
            except Exception:
                buffer[:] = b"\x00" * len(buffer)
                raise
            finally:
                key[:] = b"\x00" * len(key)
        except Exception:
            raise SecretCryptoError() from None

    def _key(self, key_ref: str) -> bytearray:
        key = self._provider.resolve_key(key_ref)
        if type(key) is not bytes or len(key) != 32:
            raise SecretCryptoError()
        return bytearray(key)
