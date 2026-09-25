"""Authorize and fully verify a private download snapshot before exposing bytes."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import BinaryIO, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.read_documents import (
    DocumentDownloadSource, DocumentReadError, DocumentReadQuery,
)

class DownloadStorageError(RuntimeError):
    """Infrastructure may report an untrusted physical file without a path."""


class DownloadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(slots=True)
class VerifiedDownload:
    document_version_id: uuid.UUID
    size_bytes: int
    detected_mime: str
    content_sha256: bytes = field(repr=False)
    stream: BinaryIO = field(repr=False)

    def close(self) -> None:
        self.stream.close()

    def __enter__(self) -> "VerifiedDownload":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class DownloadReadPort(Protocol):
    def get_download_source(self, query: DocumentReadQuery, document_id: uuid.UUID,
                            document_version_id: uuid.UUID) -> DocumentDownloadSource: ...


class DownloadStoragePort(Protocol):
    def open_verified_snapshot(self, locator: str, *, expected_sha256: bytes,
                               expected_size: int, max_bytes: int) -> BinaryIO: ...


class DownloadAuditPort(Protocol):
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID: ...


class PrepareDownloadService:
    def __init__(self, *, reader: DownloadReadPort, storage: DownloadStoragePort,
                 unit_of_work: Callable[[], object], audit: DownloadAuditPort,
                 max_bytes: int = 100_000_000) -> None:
        if (any(item is None for item in (reader, storage, unit_of_work, audit))
                or type(max_bytes) is not int or not 0 < max_bytes <= 100_000_000):
            raise ValueError("download dependencies and bounded size are required")
        self._reader, self._storage = reader, storage
        self._uow, self._audit, self._max_bytes = unit_of_work, audit, max_bytes

    def prepare(self, query: DocumentReadQuery, document_id: uuid.UUID,
                document_version_id: uuid.UUID) -> VerifiedDownload:
        source = self._source(query, document_id, document_version_id)
        try:
            snapshot = self._storage.open_verified_snapshot(
                source.storage_locator, expected_sha256=source.content_sha256,
                expected_size=source.size_bytes, max_bytes=self._max_bytes,
            )
        except DownloadStorageError:
            self._record_integrity_failure(query, source)
            raise DownloadError("FILE_INTEGRITY_MISMATCH") from None
        except Exception:
            raise DownloadError("FILE_UNAVAILABLE") from None
        try:
            current = self._source(query, document_id, document_version_id)
            if current != source:
                raise DownloadError("RESOURCE_NOT_FOUND")
            return VerifiedDownload(
                source.document_version_id, source.size_bytes,
                source.detected_mime, source.content_sha256, snapshot,
            )
        except Exception:
            snapshot.close()
            raise

    def _source(self, query: DocumentReadQuery, document_id: uuid.UUID,
                document_version_id: uuid.UUID) -> DocumentDownloadSource:
        try:
            source = self._reader.get_download_source(query, document_id,
                                                      document_version_id)
        except DocumentReadError as exc:
            raise DownloadError(exc.code) from None
        except Exception:
            raise DownloadError("DOCUMENT_UNAVAILABLE") from None
        if (type(source) is not DocumentDownloadSource
                or type(source.actor_user_id) is not uuid.UUID
                or source.actor_user_id.int == 0
                or type(source.file_object_id) is not uuid.UUID
                or source.file_object_id.int == 0
                or type(source.storage_locator) is not str
                or type(source.content_sha256) is not bytes
                or len(source.content_sha256) != 32
                or type(source.size_bytes) is not int
                or not 0 <= source.size_bytes <= self._max_bytes
                or type(source.detected_mime) is not str
                or not source.detected_mime):
            raise DownloadError("FILE_UNAVAILABLE")
        return source

    def _record_integrity_failure(self, query: DocumentReadQuery,
                                  source: DocumentDownloadSource) -> None:
        try:
            with self._uow() as tx:
                self._audit.append(tx, AuditEventDraft(
                    trace_id=query.trace_id,
                    event_scope="PROJECT" if source.scope == "PROJECT" else "DEPLOYMENT",
                    target_project_id=source.project_id,
                    actor_type="USER", actor_id=source.actor_user_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="DOCUMENT_DOWNLOAD_INTEGRITY_FAILED", outcome="FAILED",
                    target_owner_module="document", target_object_type="DOC-03",
                    target_object_id=source.file_object_id,
                    target_version_id=source.document_version_id,
                    reason_code="FILE_INTEGRITY_MISMATCH",
                ))
                tx.commit()
        except Exception:
            raise DownloadError("DOCUMENT_UNAVAILABLE") from None
