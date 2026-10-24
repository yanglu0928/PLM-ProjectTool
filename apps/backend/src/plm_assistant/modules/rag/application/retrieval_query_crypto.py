"""Provider-neutral contract for encrypted Retrieval query content."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class RetrievalQueryCryptoError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("RAG retrieval query unavailable")


class RetrievalQueryKeyProviderPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class EncryptedRetrievalQuery:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    query_fingerprint: bytes = field(repr=False)
    encrypted_payload: bytes = field(repr=False)
    encryption_metadata: dict = field(repr=False)
    key_provider_ref: str = field(repr=False)
    plaintext_bytes: int
    retention_until: datetime


@dataclass(frozen=True, slots=True)
class RetrievalQueryEnvelope:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    query_fingerprint: bytes = field(repr=False)
    encrypted_payload: bytes = field(repr=False)
    encryption_metadata: dict = field(repr=False)
    key_provider_ref: str = field(repr=False)
    plaintext_bytes: int
    retention_until: datetime
