"""Read-only GLOBAL Reference source preview; never creates an attestation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

from .reference_source_qualification import (
    ProvenReferenceSources, ReferenceSourceError, ReferenceSourceRequest,
    VerifiedReferenceDocument, VerifiedReferenceEvidence,
)


class ReferenceDeidentificationPreviewError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PreviewReferenceDeidentification:
    sources: ReferenceSourceRequest = field(repr=False)
    csrf_token: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class PreviewDocumentRef:
    document_id: uuid.UUID
    document_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ReferenceDeidentificationPreviewView:
    source_fingerprint: bytes = field(repr=False)
    document_refs: tuple[PreviewDocumentRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    previewed_at: datetime


class AdminAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SourceProofPort(Protocol):
    def prove_sources(self, transaction: object,
                      request: ReferenceSourceRequest) -> ProvenReferenceSources: ...


class ReferenceDeidentificationPreviewService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AdminAccessPort,
                 license_guard: LicensePort, sources: SourceProofPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, sources)):
            raise ValueError("GLOBAL Reference preview dependencies required")
        self._uow, self._access, self._guard, self._sources = (
            unit_of_work, access, license_guard, sources)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def preview(self, command: PreviewReferenceDeidentification,
                ) -> ReferenceDeidentificationPreviewView:
        if (type(command) is not PreviewReferenceDeidentification
                or type(command.sources) is not ReferenceSourceRequest
                or command.sources.scope != "GLOBAL" or command.sources.project_id is not None
                or type(command.sources.session_token) is not bytes
                or len(command.sources.session_token) != 32
                or type(command.sources.trace_id) is not uuid.UUID
                or command.sources.trace_id.int == 0
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32):
            raise ReferenceDeidentificationPreviewError("VALIDATION_FAILED")
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ReferenceDeidentificationPreviewError()
        now = now.astimezone(timezone.utc)
        try:
            with self._uow() as tx:
                actor = self._access.authorized_admin(
                    tx, session_token=command.sources.session_token,
                    csrf_token=command.csrf_token, now=now)
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise ReferenceDeidentificationPreviewError("AUTH_ACCESS_DENIED")
                self._guard.require_valid(trace_id=command.sources.trace_id)
                proven = self._sources.prove_sources(tx, command.sources)
                if (type(proven) is not ProvenReferenceSources
                        or proven.scope != "GLOBAL" or proven.project_id is not None
                        or type(proven.document_versions) is not tuple
                        or len(proven.document_versions) != len(command.sources.document_version_ids)
                        or type(proven.evidence) is not tuple
                        or len(proven.evidence) != len(command.sources.evidence_ids)
                        or type(proven.content_fingerprint) is not bytes
                        or len(proven.content_fingerprint) != 32):
                    raise ReferenceDeidentificationPreviewError()
                documents = []
                for fixed, identity in zip(
                        proven.document_versions, command.sources.document_version_ids):
                    if (type(fixed) is not VerifiedReferenceDocument
                            or type(fixed.document_id) is not uuid.UUID
                            or fixed.document_id.int == 0
                            or type(identity) is not uuid.UUID or identity.int == 0
                            or fixed.document_version_id != identity
                            or fixed.scope != "GLOBAL" or fixed.project_id is not None):
                        raise ReferenceDeidentificationPreviewError()
                    documents.append(PreviewDocumentRef(fixed.document_id, identity))
                for fixed, identity in zip(proven.evidence, command.sources.evidence_ids):
                    if (type(fixed) is not VerifiedReferenceEvidence
                            or type(identity) is not uuid.UUID or identity.int == 0
                            or fixed.evidence_id != identity
                            or fixed.scope != "GLOBAL" or fixed.project_id is not None):
                        raise ReferenceDeidentificationPreviewError()
                return ReferenceDeidentificationPreviewView(
                    proven.content_fingerprint, tuple(documents),
                    command.sources.evidence_ids, now)
        except ReferenceDeidentificationPreviewError:
            raise
        except ReferenceSourceError as error:
            raise ReferenceDeidentificationPreviewError(error.code) from None
        except RuntimeLicenseError:
            raise ReferenceDeidentificationPreviewError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReferenceDeidentificationPreviewError() from None
