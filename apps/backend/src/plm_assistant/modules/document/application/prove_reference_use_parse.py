"""Internal fixed ParseResult proof for Evidence use, without user browsing rights.

Only Evidence receives verified parser bytes to validate a named locator. Solution
and the project client receive an opaque Evidence digest, never this result.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Protocol

from .prove_reference_use_document import (
    ReferenceUseDocumentProof,
    ReferenceUseDocumentProofService,
)
from .read_parse_result import FixedParseResultSource, VerifiedParseResult


class ReferenceUseParseError(RuntimeError):
    def __init__(self, code: str = "PARSER_RESULT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class ParseMetadataPort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      document_version_id: uuid.UUID,
                      parse_record_id: uuid.UUID) -> FixedParseResultSource | None: ...


class ParseBytesPort(Protocol):
    def read_verified(self, *, scope: str, project_id: uuid.UUID | None,
                      result_ref_id: uuid.UUID, expected_locator: str,
                      expected_sha256: bytes, expected_size: int) -> bytes: ...


class ReferenceUseParseProofService:
    def __init__(self, *, documents: ReferenceUseDocumentProofService,
                 metadata: ParseMetadataPort,
                 storage: ParseBytesPort) -> None:
        if any(port is None for port in (documents, metadata, storage)):
            raise ValueError("Document, parse metadata and parse storage required")
        self._documents = documents
        self._metadata = metadata
        self._storage = storage

    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID) -> VerifiedParseResult:
        if (transaction is None or scope not in ("PROJECT", "GLOBAL")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(document_version_id) is not uuid.UUID
                or document_version_id.int == 0
                or type(parse_record_id) is not uuid.UUID
                or parse_record_id.int == 0):
            raise ReferenceUseParseError("VALIDATION_FAILED")
        try:
            document = self._documents.prove(
                transaction, scope=scope, project_id=project_id,
                document_version_id=document_version_id)
            if (type(document) is not ReferenceUseDocumentProof
                    or document.document_version_id != document_version_id
                    or document.scope != scope or document.project_id != project_id
                    or type(document.content_sha256) is not bytes
                    or len(document.content_sha256) != 32):
                raise ReferenceUseParseError()
            result = self._metadata.get_for_trace(
                transaction, scope=scope, project_id=project_id,
                document_version_id=document_version_id,
                parse_record_id=parse_record_id)
            if (type(result) is not FixedParseResultSource
                    or result.document_version_id != document_version_id
                    or result.parse_record_id != parse_record_id
                    or result.scope != scope or result.project_id != project_id):
                raise ReferenceUseParseError()
            result.__post_init__()
            content = self._storage.read_verified(
                scope=scope, project_id=project_id,
                result_ref_id=result.result_ref_id,
                expected_locator=result.storage_locator,
                expected_sha256=result.result_sha256,
                expected_size=result.size_bytes)
            if (type(content) is not bytes
                    or len(content) != result.size_bytes
                    or not hmac.compare_digest(
                        hashlib.sha256(content).digest(), result.result_sha256)):
                raise ReferenceUseParseError()
            try:
                payload = json.loads(content)
            except (ValueError, UnicodeDecodeError):
                raise ReferenceUseParseError() from None
            if (type(payload) is not dict or payload.get("schema_version") != "1"
                    or payload.get("document_version_id") != str(document_version_id)
                    or payload.get("source_sha256") != document.content_sha256.hex()
                    or payload.get("parser_profile") != result.parser_profile
                    or payload.get("parser_version") != result.parser_version
                    or type(payload.get("nodes")) is not list):
                raise ReferenceUseParseError()
            after_document = self._documents.prove(
                transaction, scope=scope, project_id=project_id,
                document_version_id=document_version_id)
            after_result = self._metadata.get_for_trace(
                transaction, scope=scope, project_id=project_id,
                document_version_id=document_version_id,
                parse_record_id=parse_record_id)
            if after_document != document or after_result != result:
                raise ReferenceUseParseError()
            return VerifiedParseResult(
                parse_record_id, document_version_id, result.result_ref_id,
                result.parser_profile, result.parser_version,
                document.content_sha256, result.result_sha256, content)
        except ReferenceUseParseError:
            raise
        except Exception:
            raise ReferenceUseParseError() from None
