"""Solution adapter over Document-owned authorization and physical-byte proof."""

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
from plm_assistant.modules.solution.application.reference_source_qualification import (
    VerifiedReferenceDocument,
)


class FixedDocumentProofPort(Protocol):
    def prove(self, transaction: object, query: DocumentReadQuery, *,
              document_id: uuid.UUID,
              document_version_id: uuid.UUID) -> VerifiedFixedSource: ...


class ReferenceDocumentProofAdapter:
    def __init__(self, *, identities: ReferenceVersionIdentityPort,
                 fixed_sources: FixedDocumentProofPort) -> None:
        if identities is None or fixed_sources is None:
            raise ValueError("Document identity and fixed-source proof required")
        self._identities = identities
        self._fixed_sources = fixed_sources

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, scope: str, project_id: uuid.UUID | None,
              document_version_id: uuid.UUID) -> VerifiedReferenceDocument | None:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or type(trace_id) is not uuid.UUID
                or trace_id.int == 0 or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(document_version_id) is not uuid.UUID
                or document_version_id.int == 0):
            return None
        identity = self._identities.get(
            transaction, scope=scope, project_id=project_id,
            document_version_id=document_version_id,
        )
        if (type(identity) is not ReferenceVersionIdentity
                or type(identity.document_id) is not uuid.UUID
                or identity.document_id.int == 0
                or identity.document_version_id != document_version_id
                or identity.scope != scope or identity.project_id != project_id):
            return None
        source = self._fixed_sources.prove(
            transaction, DocumentReadQuery(session_token, trace_id, scope, project_id),
            document_id=identity.document_id,
            document_version_id=document_version_id,
        )
        if (type(source) is not VerifiedFixedSource
                or type(source.facts) is not DocumentEvidenceSourceFacts
                or source.facts.document_id != identity.document_id
                or source.facts.document_version_id != document_version_id
                or source.facts.scope != scope or source.facts.project_id != project_id
                or type(source.facts.content_sha256) is not str):
            return None
        try:
            digest = bytes.fromhex(source.facts.content_sha256)
        except ValueError:
            return None
        if len(digest) != 32:
            return None
        return VerifiedReferenceDocument(
            identity.document_id, document_version_id, scope, project_id,
            source.facts.document_category, digest,
        )
