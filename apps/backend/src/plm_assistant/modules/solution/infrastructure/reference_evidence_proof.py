"""Solution adapter over Evidence-owned current, authorized locator proofs."""

from __future__ import annotations

import uuid
from typing import Protocol

from plm_assistant.modules.evidence.application.fixed_global_reference_source import (
    GlobalReferenceEvidenceQuery, VerifiedGlobalReferenceEvidence,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, VerifiedProjectEvidence,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    VerifiedReferenceEvidence,
)


class ProjectEvidencePort(Protocol):
    def prove(self, transaction: object, query: EvidenceFixedProjectQuery,
              evidence_id: uuid.UUID) -> VerifiedProjectEvidence: ...


class GlobalEvidencePort(Protocol):
    def prove(self, transaction: object, query: GlobalReferenceEvidenceQuery,
              evidence_id: uuid.UUID) -> VerifiedGlobalReferenceEvidence: ...


class ReferenceEvidenceProofAdapter:
    def __init__(self, *, project: ProjectEvidencePort,
                 global_reference: GlobalEvidencePort) -> None:
        if project is None or global_reference is None:
            raise ValueError("PROJECT and GLOBAL Evidence proof services required")
        self._project = project
        self._global = global_reference

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, scope: str, project_id: uuid.UUID | None,
              evidence_id: uuid.UUID) -> VerifiedReferenceEvidence | None:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or type(trace_id) is not uuid.UUID
                or trace_id.int == 0 or type(evidence_id) is not uuid.UUID
                or evidence_id.int == 0 or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)):
            return None
        if scope == "PROJECT":
            proof = self._project.prove(
                transaction,
                EvidenceFixedProjectQuery(session_token, trace_id, project_id),
                evidence_id,
            )
            if (type(proof) is not VerifiedProjectEvidence
                    or proof.evidence_id != evidence_id or proof.scope != "PROJECT"
                    or proof.project_id != project_id
                    or proof.observed_state != "ELIGIBLE"
                    or proof.verified_project_role not in (
                        "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")
                    or type(proof.verified_by) is not uuid.UUID
                    or proof.verified_by.int == 0):
                return None
            version = proof.document_version_id
            fingerprint = proof.content_fingerprint
        else:
            proof = self._global.prove(
                transaction, GlobalReferenceEvidenceQuery(session_token, trace_id),
                evidence_id,
            )
            if (type(proof) is not VerifiedGlobalReferenceEvidence
                    or proof.evidence_id != evidence_id or proof.scope != "GLOBAL"
                    or proof.project_id is not None
                    or type(proof.authorized_admin_id) is not uuid.UUID
                    or proof.authorized_admin_id.int == 0):
                return None
            version = proof.document_version_id
            fingerprint = proof.content_fingerprint
        if (type(version) is not uuid.UUID or version.int == 0
                or type(fingerprint) is not bytes or len(fingerprint) != 32):
            return None
        return VerifiedReferenceEvidence(
            evidence_id, version, scope, project_id, bytes(fingerprint),
        )
