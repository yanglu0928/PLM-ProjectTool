"""Current PROJECT/ELIGIBLE Evidence proof for Requirement."""

from __future__ import annotations

import uuid

from plm_assistant.modules.evidence.application.fixed_source_record import (
    LockedEvidenceSource,
)
from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)

from .fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository


class SqlAlchemyEvidenceRequirementSourceProof:
    def __init__(self, repository=None) -> None:
        self._repository = repository or SqlAlchemyEvidenceFixedSourceRepository()

    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> EvidenceRequirementSourceProof | None:
        if any(
            type(value) is not uuid.UUID or value.int == 0
            for value in (project_id, evidence_id)
        ):
            return None
        source = self._repository.get_for_trace(
            transaction, scope="PROJECT", project_id=project_id,
            evidence_id=evidence_id,
        )
        if (
            type(source) is not LockedEvidenceSource
            or source.evidence_id != evidence_id
            or source.scope != "PROJECT"
            or source.project_id != project_id
            or type(source.document_id) is not uuid.UUID
            or source.document_id.int == 0
            or type(source.document_version_id) is not uuid.UUID
            or source.document_version_id.int == 0
            or type(source.lock_version) is not int
            or source.lock_version < 0
            or type(source.content_fingerprint) is not bytes
            or len(source.content_fingerprint) != 32
        ):
            return None
        return EvidenceRequirementSourceProof(
            source.evidence_id, project_id, source.document_id,
            source.document_version_id, source.lock_version,
            bytes(source.content_fingerprint),
        )
