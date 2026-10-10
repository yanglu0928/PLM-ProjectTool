"""Solution adapter over Document-owned version authorization and byte proof."""

from __future__ import annotations

import uuid
from typing import Protocol

from plm_assistant.modules.document.application.prove_fixed_source import (
    VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts, DocumentReadQuery,
)
from plm_assistant.modules.document.application.reference_version_identity import (
    ReferenceVersionIdentity, ReferenceVersionIdentityPort,
)
from plm_assistant.modules.solution.application.prove_section_document_content import (
    SectionDocumentContentError, SectionDocumentContentProof,
)


class FixedSourcePort(Protocol):
    def prove(self, transaction: object, query: DocumentReadQuery, *,
              document_id: uuid.UUID,
              document_version_id: uuid.UUID) -> VerifiedFixedSource: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class SectionDocumentContentProofAdapter:
    def __init__(self, *, identities: ReferenceVersionIdentityPort,
                 fixed_sources: FixedSourcePort) -> None:
        if identities is None or fixed_sources is None:
            raise ValueError("Document identity and fixed-source proof required")
        self._identities = identities
        self._fixed_sources = fixed_sources

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SectionDocumentContentProof:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or not _id(trace_id)
                or not _id(project_id) or not _id(document_version_id)):
            raise SectionDocumentContentError("VALIDATION_FAILED")
        try:
            identity = self._identities.get(
                transaction, scope="PROJECT", project_id=project_id,
                document_version_id=document_version_id)
            if (type(identity) is not ReferenceVersionIdentity
                    or not _id(identity.document_id)
                    or identity.document_version_id != document_version_id
                    or identity.scope != "PROJECT"
                    or identity.project_id != project_id):
                raise SectionDocumentContentError()
            verified = self._fixed_sources.prove(
                transaction,
                DocumentReadQuery(session_token, trace_id, "PROJECT", project_id),
                document_id=identity.document_id,
                document_version_id=document_version_id)
            if (type(verified) is not VerifiedFixedSource
                    or type(verified.facts) is not DocumentEvidenceSourceFacts
                    or verified.facts.document_id != identity.document_id
                    or verified.facts.document_version_id != document_version_id
                    or verified.facts.scope != "PROJECT"
                    or verified.facts.project_id != project_id
                    or verified.facts.document_state != "ACTIVE"
                    or type(verified.facts.content_sha256) is not str):
                raise SectionDocumentContentError()
            try:
                digest = bytes.fromhex(verified.facts.content_sha256)
            except ValueError:
                raise SectionDocumentContentError() from None
            if len(digest) != 32:
                raise SectionDocumentContentError()
            return SectionDocumentContentProof(
                project_id, identity.document_id,
                document_version_id, digest)
        except SectionDocumentContentError:
            raise
        except Exception:
            raise SectionDocumentContentError() from None
