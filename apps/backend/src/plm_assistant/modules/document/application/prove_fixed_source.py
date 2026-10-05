"""Document-owned proof of a fixed source inside a caller-owned transaction.

The caller keeps the transaction open until its referencing write commits. This
service never exposes storage locators or ordinary GLOBAL browsing privileges.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from .prepare_download import DownloadError, VerifiedDownload
from .read_documents import (
    DocumentEvidenceSourceFacts, DocumentReadError, DocumentReadQuery,
)
from .read_parse_result import (
    FixedParseResultSource, ParseResultReadError, VerifiedParseResult,
)


class FixedSourceProofError(RuntimeError):
    def __init__(self, code: str = "DOCUMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class VerifiedFixedSource:
    facts: DocumentEvidenceSourceFacts
    parse_record_id: uuid.UUID | None = None
    result_ref_id: uuid.UUID | None = None
    parser_profile: str | None = None
    parser_version: str | None = None
    result_sha256: bytes | None = field(default=None, repr=False)
    parse_content: bytes | None = field(default=None, repr=False)


class FixedDocumentFactsPort(Protocol):
    def get_source_facts_for_evidence(
            self, transaction: object, query: DocumentReadQuery,
            document_id: uuid.UUID,
            document_version_id: uuid.UUID) -> DocumentEvidenceSourceFacts: ...


class VerifiedDownloadPort(Protocol):
    def prepare(self, query: DocumentReadQuery, document_id: uuid.UUID,
                document_version_id: uuid.UUID) -> VerifiedDownload: ...


class FixedParseMetadataPort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None, document_version_id: uuid.UUID,
                      parse_record_id: uuid.UUID) -> FixedParseResultSource | None: ...


class VerifiedParsePort(Protocol):
    def read(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
             document_version_id: uuid.UUID,
             parse_record_id: uuid.UUID) -> VerifiedParseResult: ...


class DocumentFixedSourceProofService:
    def __init__(self, *, documents: FixedDocumentFactsPort,
                 downloads: VerifiedDownloadPort,
                 parse_metadata: FixedParseMetadataPort,
                 parse_results: VerifiedParsePort) -> None:
        if any(item is None for item in (documents, downloads, parse_metadata, parse_results)):
            raise ValueError("fixed source proof dependencies required")
        self._documents = documents
        self._downloads = downloads
        self._parse_metadata = parse_metadata
        self._parse_results = parse_results

    def prove(self, transaction: object, query: DocumentReadQuery, *,
              document_id: uuid.UUID, document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID | None = None) -> VerifiedFixedSource:
        if (transaction is None or type(query) is not DocumentReadQuery
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or type(document_version_id) is not uuid.UUID or document_version_id.int == 0
                or parse_record_id is not None and (
                    type(parse_record_id) is not uuid.UUID or parse_record_id.int == 0)):
            raise FixedSourceProofError("RESOURCE_NOT_FOUND")
        try:
            facts = self._documents.get_source_facts_for_evidence(
                transaction, query, document_id, document_version_id,
            )
            if (type(facts) is not DocumentEvidenceSourceFacts
                    or facts.document_id != document_id
                    or facts.document_version_id != document_version_id
                    or facts.scope != query.scope or facts.project_id != query.project_id
                    or facts.document_state not in ("ACTIVE", "ARCHIVED")
                    or type(facts.content_sha256) is not str
                    or len(facts.content_sha256) != 64):
                raise FixedSourceProofError("RESOURCE_NOT_FOUND")
            try:
                source_sha256 = bytes.fromhex(facts.content_sha256)
            except ValueError:
                raise FixedSourceProofError("DOCUMENT_UNAVAILABLE") from None
            if len(source_sha256) != 32:
                raise FixedSourceProofError("DOCUMENT_UNAVAILABLE")
            if parse_record_id is None:
                self._verify_download(transaction, query, document_id, document_version_id,
                                      source_sha256)
                return VerifiedFixedSource(facts)
            locked = self._parse_metadata.get_for_trace(
                transaction, scope=query.scope, project_id=query.project_id,
                document_version_id=document_version_id,
                parse_record_id=parse_record_id,
            )
            if (type(locked) is not FixedParseResultSource
                    or locked.parse_record_id != parse_record_id
                    or locked.document_version_id != document_version_id
                    or locked.scope != query.scope or locked.project_id != query.project_id):
                raise FixedSourceProofError("RESOURCE_NOT_FOUND")
            locked.__post_init__()
            transactional_read = getattr(
                self._parse_results, "read_in_transaction", None,
            )
            if callable(transactional_read):
                parsed = transactional_read(
                    transaction, query, document_id=document_id,
                    document_version_id=document_version_id,
                    parse_record_id=parse_record_id,
                )
            else:
                parsed = self._parse_results.read(
                    query, document_id=document_id,
                    document_version_id=document_version_id,
                    parse_record_id=parse_record_id,
                )
            if (type(parsed) is not VerifiedParseResult
                    or parsed.parse_record_id != locked.parse_record_id
                    or parsed.document_version_id != locked.document_version_id
                    or parsed.result_ref_id != locked.result_ref_id
                    or parsed.parser_profile != locked.parser_profile
                    or parsed.parser_version != locked.parser_version
                    or type(parsed.source_sha256) is not bytes
                    or not hmac.compare_digest(parsed.source_sha256, source_sha256)
                    or type(parsed.result_sha256) is not bytes
                    or not hmac.compare_digest(parsed.result_sha256, locked.result_sha256)
                    or type(parsed.content) is not bytes
                    or len(parsed.content) != locked.size_bytes
                    or not hmac.compare_digest(hashlib.sha256(parsed.content).digest(),
                                               locked.result_sha256)):
                raise FixedSourceProofError("RESOURCE_NOT_FOUND")
            return VerifiedFixedSource(
                facts, locked.parse_record_id, locked.result_ref_id,
                locked.parser_profile, locked.parser_version,
                locked.result_sha256, parsed.content,
            )
        except FixedSourceProofError:
            raise
        except (DocumentReadError, DownloadError, ParseResultReadError) as error:
            raise FixedSourceProofError(error.code) from None
        except Exception:
            raise FixedSourceProofError() from None

    def _verify_download(self, transaction: object, query: DocumentReadQuery,
                         document_id: uuid.UUID,
                         version_id: uuid.UUID, source_sha256: bytes) -> None:
        transactional_prepare = getattr(
            self._downloads, "prepare_in_transaction", None,
        )
        if callable(transactional_prepare):
            snapshot = transactional_prepare(
                transaction, query, document_id, version_id,
            )
        else:
            snapshot = self._downloads.prepare(query, document_id, version_id)
        if type(snapshot) is not VerifiedDownload:
            close = getattr(snapshot, "close", None)
            if callable(close):
                close()
            raise FixedSourceProofError()
        with snapshot:
            if (snapshot.document_version_id != version_id
                    or type(snapshot.content_sha256) is not bytes
                    or not hmac.compare_digest(snapshot.content_sha256, source_sha256)
                    or type(snapshot.size_bytes) is not int
                    or not 0 <= snapshot.size_bytes <= 100_000_000
                    or type(snapshot.detected_mime) is not str
                    or not snapshot.detected_mime):
                raise FixedSourceProofError("FILE_INTEGRITY_MISMATCH")
