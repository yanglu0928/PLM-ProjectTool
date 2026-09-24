from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from plm_assistant.modules.platform.application.trace_context import (
    current_trace_id,
    new_uuid7,
)


class SecretAccessError(RuntimeError):
    """A fixed-message failure that never includes Secret or store details."""


class SecretPurpose(StrEnum):
    DATABASE_PASSWORD = "DATABASE_PASSWORD"
    AI_PROVIDER_KEY = "AI_PROVIDER_KEY"
    RERANKER_KEY = "RERANKER_KEY"
    INTEGRATION_CREDENTIAL = "INTEGRATION_CREDENTIAL"


class SecretConsumer(StrEnum):
    DATABASE_ADAPTER = "DATABASE_ADAPTER"
    AI_PROVIDER_ADAPTER = "AI_PROVIDER_ADAPTER"
    RERANKER_ADAPTER = "RERANKER_ADAPTER"
    INTEGRATION_ADAPTER = "INTEGRATION_ADAPTER"


class SecretState(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    RETIRED = "RETIRED"


_PURPOSE_CONSUMER = {
    SecretPurpose.DATABASE_PASSWORD: SecretConsumer.DATABASE_ADAPTER,
    SecretPurpose.AI_PROVIDER_KEY: SecretConsumer.AI_PROVIDER_ADAPTER,
    SecretPurpose.RERANKER_KEY: SecretConsumer.RERANKER_ADAPTER,
    SecretPurpose.INTEGRATION_CREDENTIAL: SecretConsumer.INTEGRATION_ADAPTER,
}


@dataclass(frozen=True, slots=True)
class SecretRef:
    secret_id: uuid.UUID

    def __post_init__(self) -> None:
        if not isinstance(self.secret_id, uuid.UUID) or self.secret_id.int == 0:
            raise ValueError("invalid secret reference")


@dataclass(frozen=True, slots=True)
class SecretEnvelope:
    """Internal encrypted record; sensitive bytes never appear in repr."""

    secret_ref: SecretRef
    purpose: SecretPurpose
    state: SecretState
    allowed_consumer: SecretConsumer
    version_no: int
    encrypted_payload: bytes = field(repr=False)
    encryption_metadata: bytes = field(repr=False)
    key_provider_ref: str = field(repr=False)


class EncryptedSecretStorePort(Protocol):
    def load(self, secret_ref: SecretRef) -> SecretEnvelope | None: ...


class SecretDecryptorPort(Protocol):
    """Implemented later with an external SecretKeyProvider, not a YAML key."""

    def decrypt(self, envelope: SecretEnvelope) -> bytearray: ...


class SecretAuditPort(Protocol):
    def record_access(
        self,
        *,
        secret_ref: SecretRef,
        consumer: str,
        outcome: str,
        trace_id: str,
    ) -> None: ...


class SecretResolver:
    """Fail-closed single-call access boundary for an authorized adapter."""

    def __init__(
        self,
        store: EncryptedSecretStorePort,
        decryptor: SecretDecryptorPort,
        audit: SecretAuditPort,
    ) -> None:
        self._store = store
        self._decryptor = decryptor
        self._audit = audit

    @contextmanager
    def use(
        self, secret_ref: SecretRef, consumer: SecretConsumer
    ) -> Iterator[memoryview]:
        trace_id = current_trace_id() or new_uuid7()
        safe_consumer = consumer.value if isinstance(consumer, SecretConsumer) else "UNKNOWN"
        plaintext: bytearray | None = None

        try:
            if not isinstance(secret_ref, SecretRef) or not isinstance(
                consumer, SecretConsumer
            ):
                raise SecretAccessError("secret unavailable")
            envelope = self._store.load(secret_ref)
            if (
                envelope is None
                or envelope.secret_ref != secret_ref
                or not isinstance(envelope.purpose, SecretPurpose)
                or envelope.state is not SecretState.ACTIVE
                or envelope.allowed_consumer is not consumer
                or _PURPOSE_CONSUMER.get(envelope.purpose) is not consumer
                or type(envelope.version_no) is not int
                or envelope.version_no < 1
                or type(envelope.encrypted_payload) is not bytes
                or not envelope.encrypted_payload
                or type(envelope.encryption_metadata) is not bytes
                or not envelope.encryption_metadata
                or not isinstance(envelope.key_provider_ref, str)
                or not envelope.key_provider_ref
            ):
                raise SecretAccessError("secret unavailable")
            plaintext = self._decryptor.decrypt(envelope)
            if type(plaintext) is not bytearray or not plaintext:
                raise SecretAccessError("secret unavailable")
            self._audit.record_access(
                secret_ref=secret_ref,
                consumer=safe_consumer,
                outcome="GRANTED",
                trace_id=trace_id,
            )
        except Exception:
            if isinstance(plaintext, bytearray):
                plaintext[:] = b"\x00" * len(plaintext)
            if isinstance(secret_ref, SecretRef):
                try:
                    self._audit.record_access(
                        secret_ref=secret_ref,
                        consumer=safe_consumer,
                        outcome="DENIED",
                        trace_id=trace_id,
                    )
                except Exception:
                    pass
            raise SecretAccessError("secret unavailable") from None

        view = memoryview(plaintext)
        try:
            yield view
        finally:
            view.release()
            plaintext[:] = b"\x00" * len(plaintext)
