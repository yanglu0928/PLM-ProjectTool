"""Reprove the fixed Reference source set without granting GLOBAL read access.

Only the authorized Outline Owner may call this adapter, in the same database
transaction as its Reference current-state check and eventual version write.
"""

from __future__ import annotations

import json
import uuid
from typing import Protocol

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProof,
)
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import (
    ReferenceUseEvidenceProof,
)
from plm_assistant.modules.solution.application.prove_reference_use import (
    CurrentReferenceSourceProof,
    CurrentReferenceUseSnapshot,
    ReferenceUseQuery,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    fingerprint_reference_sources,
)


class DocumentUsePort(Protocol):
    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              document_version_id: uuid.UUID) -> ReferenceUseDocumentProof: ...


class EvidenceUsePort(Protocol):
    def prove(self, transaction: object, *, scope: str,
              project_id: uuid.UUID | None,
              evidence_id: uuid.UUID) -> ReferenceUseEvidenceProof: ...


class CurrentReferenceSourceAdapter:
    def __init__(self, *, documents: DocumentUsePort,
                 evidence: EvidenceUsePort) -> None:
        if documents is None or evidence is None:
            raise ValueError("Document and Evidence current-use ports required")
        self._documents = documents
        self._evidence = evidence

    def prove(self, transaction: object, *, query: ReferenceUseQuery,
              current: CurrentReferenceUseSnapshot) -> CurrentReferenceSourceProof | None:
        if (transaction is None or type(query) is not ReferenceUseQuery
                or type(current) is not CurrentReferenceUseSnapshot
                or current.scope != query.scope
                or current.reference_solution_id != query.reference_solution_id
                or current.reference_version_id != query.reference_version_id
                or current.source_project_id != (
                    query.target_project_id if query.scope == "PROJECT" else None)
                or type(current.applicability) is not dict):
            return None
        try:
            applicability = json.dumps(
                current.applicability, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            )
            if len(applicability.encode("utf-8")) > 64_000:
                return None
            documents = []
            for version_id in current.document_version_ids:
                proof = self._documents.prove(
                    transaction, scope=current.scope,
                    project_id=current.source_project_id,
                    document_version_id=version_id)
                if (type(proof) is not ReferenceUseDocumentProof
                        or proof.document_version_id != version_id
                        or proof.scope != current.scope
                        or proof.project_id != current.source_project_id
                        or type(proof.content_sha256) is not bytes
                        or len(proof.content_sha256) != 32):
                    return None
                documents.append((version_id, proof.content_sha256))
            evidence = []
            for evidence_id in current.evidence_ids:
                proof = self._evidence.prove(
                    transaction, scope=current.scope,
                    project_id=current.source_project_id,
                    evidence_id=evidence_id)
                if (type(proof) is not ReferenceUseEvidenceProof
                        or proof.evidence_id != evidence_id
                        or type(proof.document_version_id) is not uuid.UUID
                        or proof.document_version_id.int == 0
                        or proof.scope != current.scope
                        or proof.project_id != current.source_project_id
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    return None
                evidence.append((evidence_id, proof.document_version_id,
                                 proof.content_fingerprint))
            fingerprint = fingerprint_reference_sources(
                scope=current.scope, project_id=current.source_project_id,
                documents=tuple(documents), evidence=tuple(evidence),
                source_project_class=current.source_project_class,
                deidentification_class=current.deidentification_class,
                applicability=current.applicability)
            return CurrentReferenceSourceProof(
                current.scope, current.source_project_id,
                current.document_version_ids, current.evidence_ids,
                fingerprint)
        except Exception:
            return None
