"""ReferenceSolution source admission contract; no persistence or API exposure.

Document, Evidence and human deidentification facts must come from authorized
application ports in the caller's transaction. A client may only name versions.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class ReferenceSourceError(RuntimeError):
    def __init__(self, code: str = "RESOURCE_NOT_FOUND") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReferenceSourceRequest:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_version_ids: tuple[uuid.UUID, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    source_project_class: str
    deidentification_class: str
    applicability: dict[str, object] = field(repr=False)


@dataclass(frozen=True, slots=True)
class VerifiedReferenceDocument:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_category: str
    content_sha256: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class VerifiedReferenceEvidence:
    evidence_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    content_fingerprint: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class VerifiedReferenceDeidentification:
    confirmation_id: uuid.UUID
    authorized_admin_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class QualifiedReferenceSources:
    scope: str
    project_id: uuid.UUID | None
    document_versions: tuple[VerifiedReferenceDocument, ...]
    evidence: tuple[VerifiedReferenceEvidence, ...]
    content_fingerprint: bytes = field(repr=False)
    deidentification_confirmation_id: uuid.UUID | None = None


class DocumentSourcePort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, scope: str, project_id: uuid.UUID | None,
              document_version_id: uuid.UUID) -> VerifiedReferenceDocument | None: ...


class EvidenceSourcePort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, scope: str, project_id: uuid.UUID | None,
              evidence_id: uuid.UUID) -> VerifiedReferenceEvidence | None: ...


class DeidentificationPort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, source_fingerprint: bytes,
              source_project_class: str, deidentification_class: str,
              applicability: dict[str, object]) -> VerifiedReferenceDeidentification | None: ...


_PROJECT_CATEGORIES = frozenset({
    "CONTRACTUAL", "PROJECT_RECORD", "REFERENCE_MATERIAL", "STANDARD_CAPABILITY",
})
_GLOBAL_CATEGORIES = frozenset({"REFERENCE_MATERIAL", "STANDARD_CAPABILITY"})


def _identity(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ids(values: object, *, minimum: int, maximum: int) -> bool:
    return (type(values) is tuple and minimum <= len(values) <= maximum
            and all(_identity(value) for value in values)
            and len(set(values)) == len(values))


class ReferenceSourceQualificationService:
    def __init__(self, *, documents: DocumentSourcePort,
                 evidence: EvidenceSourcePort,
                 deidentification: DeidentificationPort) -> None:
        if any(port is None for port in (documents, evidence, deidentification)):
            raise ValueError("all Reference source proof ports are required")
        self._documents = documents
        self._evidence = evidence
        self._deidentification = deidentification

    def qualify(self, transaction: object,
                request: ReferenceSourceRequest) -> QualifiedReferenceSources:
        if (transaction is None or type(request) is not ReferenceSourceRequest
                or type(request.session_token) is not bytes
                or len(request.session_token) != 32
                or not _identity(request.trace_id)
                or request.scope not in ("GLOBAL", "PROJECT")
                or request.scope == "GLOBAL" and request.project_id is not None
                or request.scope == "PROJECT" and not _identity(request.project_id)
                or not _ids(request.document_version_ids, minimum=1, maximum=100)
                or not _ids(request.evidence_ids, minimum=0, maximum=500)
                or type(request.source_project_class) is not str
                or not 1 <= len(request.source_project_class) <= 128
                or request.source_project_class != request.source_project_class.strip()
                or type(request.deidentification_class) is not str
                or not 1 <= len(request.deidentification_class) <= 128
                or request.deidentification_class != request.deidentification_class.strip()
                or type(request.applicability) is not dict):
            raise ReferenceSourceError("VALIDATION_FAILED")
        try:
            encoded_applicability = json.dumps(
                request.applicability, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            )
            if len(encoded_applicability.encode("utf-8")) > 64_000:
                raise ValueError("applicability too large")
        except (TypeError, ValueError, OverflowError):
            raise ReferenceSourceError("VALIDATION_FAILED") from None
        documents: list[VerifiedReferenceDocument] = []
        evidence: list[VerifiedReferenceEvidence] = []
        try:
            for version_id in request.document_version_ids:
                proof = self._documents.prove(
                    transaction, session_token=request.session_token,
                    trace_id=request.trace_id, scope=request.scope,
                    project_id=request.project_id,
                    document_version_id=version_id,
                )
                if (type(proof) is not VerifiedReferenceDocument
                        or not _identity(proof.document_id)
                        or proof.document_version_id != version_id
                        or proof.scope != request.scope
                        or proof.project_id != request.project_id
                        or proof.document_category not in (
                            _GLOBAL_CATEGORIES if request.scope == "GLOBAL"
                            else _PROJECT_CATEGORIES)
                        or type(proof.content_sha256) is not bytes
                        or len(proof.content_sha256) != 32):
                    raise ReferenceSourceError()
                documents.append(proof)
            for evidence_id in request.evidence_ids:
                proof = self._evidence.prove(
                    transaction, session_token=request.session_token,
                    trace_id=request.trace_id, scope=request.scope,
                    project_id=request.project_id, evidence_id=evidence_id,
                )
                if (type(proof) is not VerifiedReferenceEvidence
                        or proof.evidence_id != evidence_id
                        or not _identity(proof.document_version_id)
                        or proof.scope != request.scope
                        or proof.project_id != request.project_id
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    raise ReferenceSourceError()
                evidence.append(proof)
            canonical = json.dumps({
                "scope": request.scope,
                "project_id": str(request.project_id) if request.project_id else None,
                "documents": [[str(item.document_version_id), item.content_sha256.hex()]
                              for item in documents],
                "evidence": [[str(item.evidence_id), str(item.document_version_id),
                              item.content_fingerprint.hex()] for item in evidence],
                "source_project_class": request.source_project_class,
                "deidentification_class": request.deidentification_class,
                "applicability": request.applicability,
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
               allow_nan=False).encode("utf-8")
            fingerprint = hashlib.sha256(canonical).digest()
            confirmation_id = None
            if request.scope == "GLOBAL":
                confirmation = self._deidentification.prove(
                    transaction, session_token=request.session_token,
                    trace_id=request.trace_id, source_fingerprint=fingerprint,
                    source_project_class=request.source_project_class,
                    deidentification_class=request.deidentification_class,
                    applicability=request.applicability,
                )
                if (type(confirmation) is not VerifiedReferenceDeidentification
                        or not _identity(confirmation.confirmation_id)
                        or not _identity(confirmation.authorized_admin_id)
                        or type(confirmation.source_fingerprint) is not bytes
                        or confirmation.source_fingerprint != fingerprint
                        or type(confirmation.confirmed_at) is not datetime
                        or confirmation.confirmed_at.tzinfo is None
                        or confirmation.confirmed_at.utcoffset() is None):
                    raise ReferenceSourceError()
                confirmation_id = confirmation.confirmation_id
            return QualifiedReferenceSources(
                request.scope, request.project_id, tuple(documents), tuple(evidence),
                fingerprint, confirmation_id,
            )
        except ReferenceSourceError:
            raise
        except Exception:
            raise ReferenceSourceError("SOURCE_UNAVAILABLE") from None
