"""Opaque fixed DocumentVersion proof for a previously authorized Reference use.

This is an internal application interface, never a GLOBAL browse/read endpoint.
The caller holds its transaction through the referencing write; only the digest
escapes this service, not file bytes, storage locators or document metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import BinaryIO, Protocol


class ReferenceUseDocumentError(RuntimeError):
    def __init__(self, code: str = "DOCUMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CurrentReferenceDocumentSource:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_category: str
    content_sha256: bytes = field(repr=False)
    size_bytes: int
    detected_mime: str
    storage_locator: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReferenceUseDocumentProof:
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    content_sha256: bytes = field(repr=False)


class CurrentSourcePort(Protocol):
    def current(self, transaction: object, *, scope: str,
                project_id: uuid.UUID | None,
                document_version_id: uuid.UUID) -> CurrentReferenceDocumentSource | None: ...


class VerifiedStoragePort(Protocol):
    def open_verified_snapshot(self, locator: str, *, expected_sha256: bytes,
                               expected_size: int, max_bytes: int) -> BinaryIO: ...


class ReferenceUseDocumentProofService:
    def __init__(self, *, sources: CurrentSourcePort,
                 storage: VerifiedStoragePort) -> None:
        if sources is None or storage is None:
            raise ValueError("Document reference-use source and storage required")
        self._sources = sources
        self._storage = storage

    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              document_version_id: uuid.UUID) -> ReferenceUseDocumentProof:
        if (transaction is None or scope not in ("PROJECT", "GLOBAL")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(document_version_id) is not uuid.UUID
                or document_version_id.int == 0):
            raise ReferenceUseDocumentError("VALIDATION_FAILED")
        try:
            source = self._sources.current(
                transaction, scope=scope, project_id=project_id,
                document_version_id=document_version_id)
            if (type(source) is not CurrentReferenceDocumentSource
                    or type(source.document_id) is not uuid.UUID
                    or source.document_id.int == 0
                    or source.document_version_id != document_version_id
                    or source.scope != scope or source.project_id != project_id
                    or source.document_category not in (
                        ("REFERENCE_MATERIAL", "STANDARD_CAPABILITY")
                        if scope == "GLOBAL" else
                        ("CONTRACTUAL", "PROJECT_RECORD", "REFERENCE_MATERIAL",
                         "STANDARD_CAPABILITY"))
                    or type(source.content_sha256) is not bytes
                    or len(source.content_sha256) != 32
                    or type(source.size_bytes) is not int
                    or not 0 <= source.size_bytes <= 100_000_000
                    or type(source.detected_mime) is not str
                    or not source.detected_mime
                    or type(source.storage_locator) is not str
                    or not source.storage_locator):
                raise ReferenceUseDocumentError()
            with self._storage.open_verified_snapshot(
                    source.storage_locator,
                    expected_sha256=source.content_sha256,
                    expected_size=source.size_bytes,
                    max_bytes=100_000_000):
                pass
            return ReferenceUseDocumentProof(
                document_version_id, scope, project_id,
                source.content_sha256)
        except ReferenceUseDocumentError:
            raise
        except Exception:
            raise ReferenceUseDocumentError() from None
