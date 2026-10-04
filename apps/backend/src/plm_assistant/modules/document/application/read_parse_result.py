"""Document-owned, authorized read of a fixed published Parser result.

The returned bytes remain an internal Port value. Evidence must validate a
specific node/locator separately before creating a business reference.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .read_documents import (
    DocumentReadQuery,
)
from .prepare_download import DownloadError, VerifiedDownload


class ParseResultReadError(RuntimeError):
    def __init__(self, code: str = "DOCUMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FixedParseResultSource:
    parse_record_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    parser_profile: str
    parser_version: str
    result_ref_id: uuid.UUID
    storage_locator: str = field(repr=False)
    result_sha256: bytes = field(repr=False)
    size_bytes: int
    result_schema_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.parse_record_id, self.document_version_id, self.result_ref_id))
                or self.scope not in ("GLOBAL", "PROJECT")
                or self.scope == "GLOBAL" and self.project_id is not None
                or self.scope == "PROJECT" and (
                    type(self.project_id) is not uuid.UUID or self.project_id.int == 0)
                or type(self.parser_profile) is not str or not self.parser_profile
                or type(self.parser_version) is not str or not self.parser_version
                or type(self.storage_locator) is not str or not self.storage_locator
                or type(self.result_sha256) is not bytes or len(self.result_sha256) != 32
                or type(self.size_bytes) is not int or not 1 <= self.size_bytes <= 100_000_000
                or self.result_schema_version != 1):
            raise ParseResultReadError()


@dataclass(frozen=True, slots=True)
class VerifiedParseResult:
    parse_record_id: uuid.UUID
    document_version_id: uuid.UUID
    result_ref_id: uuid.UUID
    parser_profile: str
    parser_version: str
    source_sha256: bytes = field(repr=False)
    result_sha256: bytes = field(repr=False)
    content: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class _FixedDocumentProof:
    document_version_id: uuid.UUID
    content_sha256: bytes = field(repr=False)
    size_bytes: int
    detected_mime: str


class AuthorizedDocumentPort(Protocol):
    def prepare(self, query: DocumentReadQuery, document_id: uuid.UUID,
                document_version_id: uuid.UUID) -> VerifiedDownload: ...


class ParseMetadataPort(Protocol):
    def get(self, transaction: object, *, scope: str, project_id: uuid.UUID | None,
            document_version_id: uuid.UUID,
            parse_record_id: uuid.UUID) -> FixedParseResultSource | None: ...


class ParseBytesPort(Protocol):
    def read_verified(self, *, scope: str, project_id: uuid.UUID | None,
                      result_ref_id: uuid.UUID, expected_locator: str,
                      expected_sha256: bytes, expected_size: int) -> bytes: ...


class DocumentParseResultReadService:
    def __init__(self, *, documents: AuthorizedDocumentPort,
                 metadata: ParseMetadataPort, storage: ParseBytesPort,
                 unit_of_work: Callable[[], object]) -> None:
        if any(value is None for value in (documents, metadata, storage, unit_of_work)):
            raise ValueError("Document result read dependencies required")
        self._documents, self._metadata = documents, metadata
        self._storage, self._uow = storage, unit_of_work

    def read(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
             document_version_id: uuid.UUID,
             parse_record_id: uuid.UUID) -> VerifiedParseResult:
        if (type(query) is not DocumentReadQuery
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or type(document_version_id) is not uuid.UUID or document_version_id.int == 0
                or type(parse_record_id) is not uuid.UUID or parse_record_id.int == 0):
            raise ParseResultReadError("RESOURCE_NOT_FOUND")
        first_document = self._document(query, document_id, document_version_id)
        first_result = self._result(query, document_version_id, parse_record_id)
        try:
            content = self._storage.read_verified(
                scope=query.scope, project_id=query.project_id,
                result_ref_id=first_result.result_ref_id,
                expected_locator=first_result.storage_locator,
                expected_sha256=first_result.result_sha256,
                expected_size=first_result.size_bytes,
            )
        except Exception:
            raise ParseResultReadError("FILE_INTEGRITY_MISMATCH") from None
        if type(content) is not bytes or len(content) != first_result.size_bytes:
            raise ParseResultReadError("FILE_INTEGRITY_MISMATCH")
        if not hmac.compare_digest(hashlib.sha256(content).digest(), first_result.result_sha256):
            raise ParseResultReadError("FILE_INTEGRITY_MISMATCH")
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeDecodeError):
            raise ParseResultReadError("PARSER_RESULT_INVALID") from None
        if (type(payload) is not dict or payload.get("schema_version") != "1"
                or payload.get("document_version_id") != str(document_version_id)
                or payload.get("source_sha256") != first_document.content_sha256.hex()
                or payload.get("parser_profile") != first_result.parser_profile
                or payload.get("parser_version") != first_result.parser_version
                or type(payload.get("nodes")) is not list):
            raise ParseResultReadError("PARSER_RESULT_INVALID")
        if (self._document(query, document_id, document_version_id) != first_document
                or self._result(query, document_version_id, parse_record_id) != first_result):
            raise ParseResultReadError("RESOURCE_NOT_FOUND")
        return VerifiedParseResult(
            parse_record_id, document_version_id, first_result.result_ref_id,
            first_result.parser_profile, first_result.parser_version,
            first_document.content_sha256, first_result.result_sha256, content,
        )

    def _document(self, query: DocumentReadQuery, document_id: uuid.UUID,
                  version_id: uuid.UUID) -> _FixedDocumentProof:
        try:
            snapshot = self._documents.prepare(query, document_id, version_id)
        except DownloadError as error:
            raise ParseResultReadError(error.code) from None
        except Exception:
            raise ParseResultReadError() from None
        if type(snapshot) is not VerifiedDownload:
            close = getattr(snapshot, "close", None)
            if callable(close):
                close()
            raise ParseResultReadError()
        try:
            with snapshot:
                if (snapshot.document_version_id != version_id
                        or type(snapshot.content_sha256) is not bytes
                        or len(snapshot.content_sha256) != 32
                        or type(snapshot.size_bytes) is not int
                        or not 0 <= snapshot.size_bytes <= 100_000_000
                        or type(snapshot.detected_mime) is not str
                        or not snapshot.detected_mime):
                    raise ParseResultReadError()
                return _FixedDocumentProof(
                    snapshot.document_version_id, snapshot.content_sha256,
                    snapshot.size_bytes, snapshot.detected_mime,
                )
        except ParseResultReadError:
            raise
        except Exception:
            raise ParseResultReadError() from None

    def _result(self, query: DocumentReadQuery, version_id: uuid.UUID,
                record_id: uuid.UUID) -> FixedParseResultSource:
        try:
            with self._uow() as tx:
                source = self._metadata.get(
                    tx, scope=query.scope, project_id=query.project_id,
                    document_version_id=version_id, parse_record_id=record_id,
                )
            if (type(source) is not FixedParseResultSource
                    or source.document_version_id != version_id
                    or source.parse_record_id != record_id
                    or source.scope != query.scope or source.project_id != query.project_id):
                raise ParseResultReadError("RESOURCE_NOT_FOUND")
            source.__post_init__()
            return source
        except ParseResultReadError:
            raise
        except Exception:
            raise ParseResultReadError() from None
