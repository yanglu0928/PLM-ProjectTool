"""Evidence-side proof through the authorized DocumentService snapshot Port.

Only whole-document positions are currently resolvable. Precise locators must
wait for a source-format resolver and cannot reuse a whole-file fingerprint.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.document.application.prepare_download import (
    DownloadError, VerifiedDownload,
)
from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.evidence.domain.locator import (
    EvidenceLocatorError, validate_evidence_locator,
)


class EvidenceSourceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceDocumentProof:
    document_version_id: uuid.UUID
    locator: dict[str, object]
    content_fingerprint: bytes = field(repr=False)
    precision: str = "DOCUMENT"


class EvidenceDocumentSnapshotPort(Protocol):
    def prepare(self, query: DocumentReadQuery, document_id: uuid.UUID,
                document_version_id: uuid.UUID) -> VerifiedDownload: ...


class DocumentEvidenceProofService:
    def __init__(self, *, document_snapshots: EvidenceDocumentSnapshotPort) -> None:
        if document_snapshots is None:
            raise ValueError("DocumentService snapshot Port is required")
        self._snapshots = document_snapshots

    def prove(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
              document_version_id: uuid.UUID,
              locator: object) -> EvidenceDocumentProof:
        if (type(query) is not DocumentReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or query.scope not in ("GLOBAL", "PROJECT")
                or query.scope == "GLOBAL" and query.project_id is not None
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or query.project_id.int == 0)
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or type(document_version_id) is not uuid.UUID or document_version_id.int == 0):
            raise EvidenceSourceError("VALIDATION_FAILED")
        try:
            canonical = validate_evidence_locator(locator)
        except EvidenceLocatorError:
            raise EvidenceSourceError("EVIDENCE_LOCATOR_INVALID") from None
        if canonical["locator_type"] != "DOCUMENT":
            raise EvidenceSourceError("EVIDENCE_RESOLUTION_UNAVAILABLE")
        try:
            snapshot = self._snapshots.prepare(query, document_id, document_version_id)
        except DownloadError as exc:
            raise EvidenceSourceError(exc.code) from None
        except Exception:
            raise EvidenceSourceError("DOCUMENT_UNAVAILABLE") from None
        if type(snapshot) is not VerifiedDownload:
            close = getattr(snapshot, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            raise EvidenceSourceError("DOCUMENT_UNAVAILABLE")
        try:
            with snapshot:
                if (snapshot.document_version_id != document_version_id
                        or type(snapshot.content_sha256) is not bytes
                        or len(snapshot.content_sha256) != 32
                        or type(snapshot.size_bytes) is not int
                        or not 0 <= snapshot.size_bytes <= 100_000_000):
                    raise EvidenceSourceError("DOCUMENT_UNAVAILABLE")
                return EvidenceDocumentProof(
                    document_version_id=document_version_id,
                    locator=canonical,
                    content_fingerprint=snapshot.content_sha256,
                )
        except EvidenceSourceError:
            raise
        except Exception:
            raise EvidenceSourceError("DOCUMENT_UNAVAILABLE") from None
