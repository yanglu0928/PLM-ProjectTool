"""Adapt Evidence Owner proofs to Workflow observations in the caller transaction.

This is source evidence only. It never proves a Review, exception or Gate verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, VerifiedProjectEvidence,
)
from plm_assistant.modules.evidence.application.fixed_global_standard_source import (
    StandardEvidenceQuery, VerifiedStandardEvidence,
)

from .current_checklist_record import ChecklistBasisObservation


class WorkflowEvidenceProofError(RuntimeError):
    """Fail closed without returning source content or an internal path."""


@dataclass(frozen=True, slots=True)
class WorkflowEvidenceQuery:
    session_token: bytes = field(repr=False)
    trace_id: UUID
    project_id: UUID
    evidence_id: UUID
    scope: str


class ProjectEvidenceOwner(Protocol):
    def prove(self, transaction: object, query: EvidenceFixedProjectQuery,
              evidence_id: UUID) -> VerifiedProjectEvidence: ...


class GlobalStandardEvidenceOwner(Protocol):
    def prove(self, transaction: object, query: StandardEvidenceQuery,
              evidence_id: UUID) -> VerifiedStandardEvidence: ...


class WorkflowFixedEvidenceProofService:
    def __init__(self, *, project: ProjectEvidenceOwner,
                 global_standard: GlobalStandardEvidenceOwner) -> None:
        if project is None or global_standard is None:
            raise ValueError("both Evidence Owners required")
        self._project = project
        self._global_standard = global_standard

    def prove(self, transaction: object, query: WorkflowEvidenceQuery) -> ChecklistBasisObservation:
        if (transaction is None or type(query) is not WorkflowEvidenceQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or any(type(value) is not UUID or value.int == 0 for value in
                       (query.trace_id, query.project_id, query.evidence_id))
                or query.scope not in ("PROJECT", "GLOBAL")):
            raise WorkflowEvidenceProofError("EVIDENCE_RESOLUTION_UNAVAILABLE")
        try:
            if query.scope == "PROJECT":
                result = self._project.prove(
                    transaction,
                    EvidenceFixedProjectQuery(query.session_token, query.trace_id, query.project_id),
                    query.evidence_id,
                )
                valid = (type(result) is VerifiedProjectEvidence
                         and result.project_id == query.project_id)
                ref_project_id = query.project_id
            else:
                result = self._global_standard.prove(
                    transaction,
                    StandardEvidenceQuery(query.session_token, query.trace_id, query.project_id),
                    query.evidence_id,
                )
                valid = (type(result) is VerifiedStandardEvidence
                         and result.target_project_id == query.project_id
                         and result.source_project_id is None)
                ref_project_id = None
            if (not valid or result.evidence_id != query.evidence_id
                    or result.scope != query.scope or result.observed_state != "ELIGIBLE"
                    or type(result.observed_lock_version) is not int
                    or not 0 <= result.observed_lock_version < 2**63
                    or type(result.content_fingerprint) is not bytes
                    or len(result.content_fingerprint) != 32):
                raise WorkflowEvidenceProofError("EVIDENCE_RESOLUTION_UNAVAILABLE")
            return ChecklistBasisObservation(
                ref_kind="EVIDENCE", ref_id=result.evidence_id,
                ref_scope=query.scope, ref_project_id=ref_project_id,
                observed_state="ELIGIBLE",
                observed_lock_version=result.observed_lock_version,
                content_fingerprint=result.content_fingerprint,
                verified_at=datetime.now(timezone.utc), proof_schema_version=1,
            )
        except WorkflowEvidenceProofError:
            raise
        except Exception:
            raise WorkflowEvidenceProofError("EVIDENCE_RESOLUTION_UNAVAILABLE") from None
