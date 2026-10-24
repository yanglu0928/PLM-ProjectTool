"""Opaque current Evidence proof for an authorized ReferenceVersion use.

The service is internal: Solution supplies fixed IDs after its own current
eligibility and actor checks. No Locator, parser bytes or file path escapes.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProof,
)
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult

from .fixed_source_record import LockedEvidenceSource
from .parsed_node_proof import ParsedNodeEvidenceProofService
from ..domain.locator import validate_evidence_locator


class ReferenceUseEvidenceError(RuntimeError):
    def __init__(self, code: str = "EVIDENCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReferenceUseEvidenceProof:
    evidence_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    content_fingerprint: bytes = field(repr=False)


class EvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class DocumentPort(Protocol):
    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              document_version_id: uuid.UUID) -> ReferenceUseDocumentProof: ...


class ParsePort(Protocol):
    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              document_version_id: uuid.UUID,
              parse_record_id: uuid.UUID) -> VerifiedParseResult: ...


class ReferenceUseEvidenceProofService:
    def __init__(self, *, evidence: EvidencePort,
                 documents: DocumentPort, parses: ParsePort) -> None:
        if any(port is None for port in (evidence, documents, parses)):
            raise ValueError("Evidence, Document and Parse proof ports required")
        self._evidence = evidence
        self._documents = documents
        self._parses = parses

    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              evidence_id: uuid.UUID) -> ReferenceUseEvidenceProof:
        if (transaction is None or scope not in ("PROJECT", "GLOBAL")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(evidence_id) is not uuid.UUID or evidence_id.int == 0):
            raise ReferenceUseEvidenceError("VALIDATION_FAILED")
        try:
            source = self._evidence.get_for_trace(
                transaction, scope=scope, project_id=project_id,
                evidence_id=evidence_id)
            if (type(source) is not LockedEvidenceSource
                    or source.evidence_id != evidence_id
                    or source.scope != scope or source.project_id != project_id
                    or type(source.document_id) is not uuid.UUID
                    or source.document_id.int == 0
                    or type(source.document_version_id) is not uuid.UUID
                    or source.document_version_id.int == 0
                    or type(source.lock_version) is not int
                    or source.lock_version < 0
                    or type(source.content_fingerprint) is not bytes
                    or len(source.content_fingerprint) != 32):
                raise ReferenceUseEvidenceError()
            locator = validate_evidence_locator(source.locator)
            document = self._documents.prove(
                transaction, scope=scope, project_id=project_id,
                document_version_id=source.document_version_id)
            if (type(document) is not ReferenceUseDocumentProof
                    or document.document_version_id != source.document_version_id
                    or document.scope != scope or document.project_id != project_id
                    or type(document.content_sha256) is not bytes
                    or len(document.content_sha256) != 32):
                raise ReferenceUseEvidenceError()
            parse_id = source.source_parse_record_id
            if locator["locator_type"] == "DOCUMENT":
                if parse_id is not None:
                    raise ReferenceUseEvidenceError()
                fingerprint = document.content_sha256
            else:
                if type(parse_id) is not uuid.UUID or parse_id.int == 0:
                    raise ReferenceUseEvidenceError()
                parsed = self._parses.prove(
                    transaction, scope=scope, project_id=project_id,
                    document_version_id=source.document_version_id,
                    parse_record_id=parse_id)
                if (type(parsed) is not VerifiedParseResult
                        or parsed.document_version_id != source.document_version_id
                        or parsed.parse_record_id != parse_id
                        or type(parsed.source_sha256) is not bytes
                        or not hmac.compare_digest(
                            parsed.source_sha256, document.content_sha256)):
                    raise ReferenceUseEvidenceError()
                node = ParsedNodeEvidenceProofService.prove_verified(
                    parsed, document_version_id=source.document_version_id,
                    parse_record_id=parse_id, locator=locator)
                if (node.locator != locator
                        or node.document_version_id != source.document_version_id
                        or node.parse_record_id != parse_id
                        or type(node.source_sha256) is not bytes
                        or not hmac.compare_digest(
                            node.source_sha256, document.content_sha256)):
                    raise ReferenceUseEvidenceError()
                fingerprint = node.content_fingerprint
            if (type(fingerprint) is not bytes or len(fingerprint) != 32
                    or not hmac.compare_digest(
                        fingerprint, source.content_fingerprint)):
                raise ReferenceUseEvidenceError()
            return ReferenceUseEvidenceProof(
                evidence_id, source.document_version_id, scope, project_id,
                fingerprint)
        except ReferenceUseEvidenceError:
            raise
        except Exception:
            raise ReferenceUseEvidenceError() from None
