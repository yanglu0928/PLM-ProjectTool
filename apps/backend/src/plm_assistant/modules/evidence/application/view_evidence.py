"""Authorized fixed-version Evidence viewer descriptor; no file paths or HTML."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadQuery, DocumentVersionView,
)
from plm_assistant.modules.evidence.application.document_source_proof import (
    EvidenceDocumentProof, EvidenceSourceError,
)
from plm_assistant.modules.evidence.application.parsed_node_proof import (
    EvidenceNodeProofError, EvidenceParsedNodeProof,
)
from plm_assistant.modules.evidence.application.read_evidence import (
    EvidenceReadError, EvidenceReadQuery, EvidenceView,
)
from plm_assistant.modules.evidence.domain.locator import (
    EvidenceLocatorError, validate_evidence_locator,
)


class EvidenceViewerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceViewerDescriptor:
    evidence_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_no: int
    detected_mime: str
    size_bytes: int
    locator: dict[str, object]
    precision: str
    display_label: str
    short_preview: str | None


class EvidenceReadPort(Protocol):
    def get(self, query: EvidenceReadQuery, evidence_id: uuid.UUID) -> EvidenceView: ...


class DocumentVersionPort(Protocol):
    def get_version(self, query: DocumentReadQuery, document_id: uuid.UUID,
                    document_version_id: uuid.UUID) -> DocumentVersionView: ...


class DocumentProofPort(Protocol):
    def prove(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
              document_version_id: uuid.UUID, locator: object) -> EvidenceDocumentProof: ...


class ParsedNodeProofPort(Protocol):
    def prove(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
              document_version_id: uuid.UUID, parse_record_id: uuid.UUID,
              locator: object) -> EvidenceParsedNodeProof: ...


class EvidenceViewerService:
    def __init__(self, *, evidence: EvidenceReadPort, versions: DocumentVersionPort,
                 document_proof: DocumentProofPort, node_proof: ParsedNodeProofPort) -> None:
        if any(item is None for item in (evidence, versions, document_proof, node_proof)):
            raise ValueError("Evidence viewer dependencies required")
        self._evidence, self._versions = evidence, versions
        self._document_proof, self._node_proof = document_proof, node_proof

    def view(self, query: EvidenceReadQuery, evidence_id: uuid.UUID) -> EvidenceViewerDescriptor:
        if (type(query) is not EvidenceReadQuery or type(evidence_id) is not uuid.UUID
                or evidence_id.int == 0):
            raise EvidenceViewerError("RESOURCE_NOT_FOUND")
        try:
            view = self._evidence.get(query, evidence_id)
            if (type(view) is not EvidenceView or view.evidence_id != evidence_id
                    or view.scope != query.scope or view.project_id != query.project_id):
                raise EvidenceViewerError("RESOURCE_NOT_FOUND")
            try:
                locator = validate_evidence_locator(view.locator)
            except EvidenceLocatorError:
                raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE") from None
            document_query = DocumentReadQuery(
                query.session_token, query.trace_id, query.scope, query.project_id,
            )
            version = self._versions.get_version(
                document_query, view.document_id, view.document_version_id,
            )
            if (type(version) is not DocumentVersionView
                    or version.document_id != view.document_id
                    or version.document_version_id != view.document_version_id
                    or version.availability_state != "AVAILABLE"):
                raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE")
            if locator["locator_type"] == "DOCUMENT":
                if view.source_parse_record_id is not None:
                    raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE")
                proof = self._document_proof.prove(
                    document_query, document_id=view.document_id,
                    document_version_id=view.document_version_id, locator=locator,
                )
                if type(proof) is not EvidenceDocumentProof:
                    raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE")
            else:
                record_id = view.source_parse_record_id
                if locator["locator_type"] == "STRUCTURED_NODE":
                    embedded = uuid.UUID(locator["parse_record_id"])
                    if record_id is not None and record_id != embedded:
                        raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE")
                    record_id = embedded
                if type(record_id) is not uuid.UUID or record_id.int == 0:
                    raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE")
                proof = self._node_proof.prove(
                    document_query, document_id=view.document_id,
                    document_version_id=view.document_version_id,
                    parse_record_id=record_id, locator=locator,
                )
                if (type(proof) is not EvidenceParsedNodeProof
                        or proof.parse_record_id != record_id
                        or type(proof.source_sha256) is not bytes
                        or len(proof.source_sha256) != 32
                        or not hmac.compare_digest(proof.source_sha256.hex(), version.content_sha256)):
                    raise EvidenceViewerError("EVIDENCE_FINGERPRINT_MISMATCH")
            if (proof.document_version_id != view.document_version_id
                    or proof.locator != locator
                    or type(proof.content_fingerprint) is not bytes
                    or len(proof.content_fingerprint) != 32
                    or type(view.content_fingerprint) is not bytes
                    or len(view.content_fingerprint) != 32
                    or not hmac.compare_digest(proof.content_fingerprint, view.content_fingerprint)
                    or (locator["locator_type"] == "DOCUMENT" and not hmac.compare_digest(
                        proof.content_fingerprint.hex(), version.content_sha256))):
                raise EvidenceViewerError("EVIDENCE_FINGERPRINT_MISMATCH")
            return EvidenceViewerDescriptor(
                evidence_id, view.scope, view.project_id, view.document_id,
                view.document_version_id, version.version_no, version.detected_mime,
                version.size_bytes, locator, proof.precision,
                view.display_label, view.display_excerpt,
            )
        except EvidenceViewerError:
            raise
        except EvidenceReadError as error:
            raise EvidenceViewerError(error.code) from None
        except (DocumentReadError, EvidenceSourceError, EvidenceNodeProofError) as error:
            code = error.code
            if code in ("AUTH_ACCESS_DENIED", "LICENSE_OPERATION_DENIED", "RESOURCE_NOT_FOUND"):
                raise EvidenceViewerError(code) from None
            if code == "EVIDENCE_FINGERPRINT_MISMATCH" or code == "FILE_INTEGRITY_MISMATCH":
                raise EvidenceViewerError("EVIDENCE_FINGERPRINT_MISMATCH") from None
            raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE") from None
        except Exception:
            raise EvidenceViewerError("EVIDENCE_RESOLUTION_UNAVAILABLE") from None
