"""Dedicated AES-GCM cipher for Retrieval query content, never API Secrets."""

from __future__ import annotations

import base64
import json
import re
import secrets
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    EncryptedRetrievalQuery,
    RetrievalQueryCryptoError,
    RetrievalQueryEnvelope,
    RetrievalQueryKeyProviderPort,
)


_FORMAT = "RAG-QUERY-AES-256-GCM-V1"
_KEY_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,254}$")


def _aad(run_id: uuid.UUID, project_id: uuid.UUID, fingerprint: bytes,
         key_ref: str, retention_until: datetime) -> bytes:
    if (any(type(value) is not uuid.UUID or not value.int
            for value in (run_id, project_id))
            or type(fingerprint) is not bytes or len(fingerprint) != 32
            or type(key_ref) is not str or _KEY_REF.fullmatch(key_ref) is None
            or not isinstance(retention_until, datetime)
            or retention_until.tzinfo is None
            or retention_until.utcoffset() is None):
        raise RetrievalQueryCryptoError()
    return json.dumps({
        "domain": "plm-rag-query-v1",
        "retrieval_run_id": str(run_id),
        "project_id": str(project_id),
        "query_fingerprint": fingerprint.hex(),
        "key_ref": key_ref,
        "retention_until": retention_until.astimezone(timezone.utc).isoformat(),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class AesGcmRetrievalQueryCrypto:
    def __init__(self, provider: RetrievalQueryKeyProviderPort, *, key_ref: str) -> None:
        if (provider is None or type(key_ref) is not str
                or _KEY_REF.fullmatch(key_ref) is None):
            raise ValueError("trusted Retrieval query key provider required")
        self._provider, self._key_ref = provider, key_ref

    def encrypt(self, *, retrieval_run_id: uuid.UUID, project_id: uuid.UUID,
                query_fingerprint: bytes, plaintext: bytearray,
                retention_until: datetime) -> EncryptedRetrievalQuery:
        try:
            if type(plaintext) is not bytearray or not 1 <= len(plaintext) <= 16384:
                raise RetrievalQueryCryptoError()
            aad = _aad(retrieval_run_id, project_id, query_fingerprint,
                       self._key_ref, retention_until)
            key = self._key(self._key_ref)
            nonce = secrets.token_bytes(12)
            try:
                ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
            finally:
                key[:] = b"\x00" * len(key)
            return EncryptedRetrievalQuery(
                retrieval_run_id, project_id, query_fingerprint, ciphertext,
                {"format": _FORMAT,
                 "nonce": base64.b64encode(nonce).decode("ascii")},
                self._key_ref, len(plaintext), retention_until.astimezone(timezone.utc),
            )
        except Exception:
            raise RetrievalQueryCryptoError() from None
        finally:
            if type(plaintext) is bytearray:
                plaintext[:] = b"\x00" * len(plaintext)

    def decrypt(self, envelope: RetrievalQueryEnvelope) -> bytearray:
        buffer: bytearray | None = None
        try:
            if (type(envelope) is not RetrievalQueryEnvelope
                    or type(envelope.encrypted_payload) is not bytes
                    or not 17 <= len(envelope.encrypted_payload) <= 65536
                    or type(envelope.encryption_metadata) is not dict
                    or set(envelope.encryption_metadata) != {"format", "nonce"}
                    or envelope.encryption_metadata.get("format") != _FORMAT
                    or type(envelope.encryption_metadata.get("nonce")) is not str
                    or type(envelope.plaintext_bytes) is not int
                    or not 1 <= envelope.plaintext_bytes <= 16384):
                raise RetrievalQueryCryptoError()
            nonce = base64.b64decode(
                envelope.encryption_metadata["nonce"], validate=True)
            if (len(nonce) != 12
                    or base64.b64encode(nonce).decode("ascii")
                    != envelope.encryption_metadata["nonce"]):
                raise RetrievalQueryCryptoError()
            aad = _aad(
                envelope.retrieval_run_id, envelope.project_id,
                envelope.query_fingerprint, envelope.key_provider_ref,
                envelope.retention_until,
            )
            key = self._key(envelope.key_provider_ref)
            buffer = bytearray(envelope.plaintext_bytes)
            try:
                AESGCM(key).decrypt_into(
                    nonce, envelope.encrypted_payload, aad, buffer)
                return buffer
            finally:
                key[:] = b"\x00" * len(key)
        except Exception:
            if buffer is not None:
                buffer[:] = b"\x00" * len(buffer)
            raise RetrievalQueryCryptoError() from None

    def _key(self, key_ref: str) -> bytearray:
        key = self._provider.resolve_key(key_ref)
        if type(key) is not bytes or len(key) != 32:
            raise RetrievalQueryCryptoError()
        return bytearray(key)
