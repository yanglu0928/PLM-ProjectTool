"""Narrow Evidence-owned physical source proof to SectionVersion facts."""

from __future__ import annotations

import uuid
from typing import Protocol

from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, VerifiedProjectEvidence,
)
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS
from plm_assistant.modules.solution.application.prove_section_evidence_use import (
    SectionEvidenceUseError, SectionEvidenceUseProof,
)


_WRITE_ROLES = frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})


class FixedEvidencePort(Protocol):
    def prove(self, transaction: object, query: EvidenceFixedProjectQuery,
              evidence_id: uuid.UUID) -> VerifiedProjectEvidence: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class SectionEvidenceUseProofAdapter:
    def __init__(self, *, fixed_sources: FixedEvidencePort,
                 allowed_project_roles: frozenset[str] = _WRITE_ROLES) -> None:
        if (fixed_sources is None or type(allowed_project_roles) is not frozenset
                or not allowed_project_roles
                or not allowed_project_roles <= ALL_MEMBERS):
            raise ValueError("fixed PROJECT Evidence source required")
        self._fixed_sources = fixed_sources
        self._allowed_project_roles = allowed_project_roles

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              evidence_id: uuid.UUID) -> SectionEvidenceUseProof:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or not _id(trace_id)
                or not _id(project_id) or not _id(evidence_id)):
            raise SectionEvidenceUseError("VALIDATION_FAILED")
        try:
            verified = self._fixed_sources.prove(
                transaction,
                EvidenceFixedProjectQuery(session_token, trace_id, project_id),
                evidence_id)
            if (type(verified) is not VerifiedProjectEvidence
                    or verified.evidence_id != evidence_id
                    or verified.project_id != project_id
                    or verified.scope != "PROJECT"
                    or verified.observed_state != "ELIGIBLE"
                    or not _id(verified.verified_by)
                    or verified.verified_project_role not in self._allowed_project_roles
                    or not _id(verified.document_id)
                    or not _id(verified.document_version_id)
                    or type(verified.observed_lock_version) is not int
                    or verified.observed_lock_version < 0
                    or type(verified.content_fingerprint) is not bytes
                    or len(verified.content_fingerprint) != 32):
                raise SectionEvidenceUseError()
            return SectionEvidenceUseProof(
                evidence_id, project_id, verified.document_id,
                verified.document_version_id, verified.observed_lock_version,
                verified.content_fingerprint)
        except SectionEvidenceUseError:
            raise
        except Exception:
            raise SectionEvidenceUseError() from None
