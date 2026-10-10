"""Survey Round PROJECT_RECORD proof and append shapes; no HTTP or commit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery,
    VerifiedProjectEvidence,
)


_ROUND_RECORD_ROLES = frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})


class SurveyRoundSourceError(RuntimeError):
    def __init__(self, code: str = "ROUND_SOURCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyRoundSourceQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    evidence_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class VerifiedRoundProjectRecord:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    recorded_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class SurveyRoundSourceAppend:
    survey_round_id: uuid.UUID
    project_id: uuid.UUID
    question_id: uuid.UUID | None
    verified_source: VerifiedRoundProjectRecord
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class SurveyRoundSourceRecord:
    round_source_record_ref_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    question_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    evidence_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    recorded_by: uuid.UUID
    recorded_at: datetime
    ordinal: int
    created_at: datetime


class ProjectEvidenceOwner(Protocol):
    def prove(
        self,
        transaction: object,
        query: EvidenceFixedProjectQuery,
        evidence_id: uuid.UUID,
    ) -> VerifiedProjectEvidence: ...


class SurveyRoundProjectRecordProofService:
    """Adapt a category/role-configured Evidence Owner to a Round source proof."""

    def __init__(self, *, evidence: ProjectEvidenceOwner) -> None:
        if evidence is None:
            raise ValueError("PROJECT_RECORD Evidence Owner required")
        self._evidence = evidence

    def prove(
        self,
        transaction: object,
        query: SurveyRoundSourceQuery,
    ) -> VerifiedRoundProjectRecord:
        if (transaction is None or type(query) is not SurveyRoundSourceQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    query.trace_id, query.project_id, query.evidence_id,
                ))):
            raise SurveyRoundSourceError("RESOURCE_NOT_FOUND")
        try:
            proof = self._evidence.prove(
                transaction,
                EvidenceFixedProjectQuery(
                    query.session_token, query.trace_id, query.project_id,
                ),
                query.evidence_id,
            )
            if (type(proof) is not VerifiedProjectEvidence
                    or proof.evidence_id != query.evidence_id
                    or proof.project_id != query.project_id
                    or proof.scope != "PROJECT"
                    or proof.observed_state != "ELIGIBLE"
                    or proof.document_category != "PROJECT_RECORD"
                    or proof.verified_project_role not in _ROUND_RECORD_ROLES
                    or type(proof.verified_by) is not uuid.UUID
                    or proof.verified_by.int == 0
                    or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                        proof.document_id, proof.document_version_id,
                    ))
                    or type(proof.observed_lock_version) is not int
                    or not 0 <= proof.observed_lock_version < 2**63
                    or type(proof.content_fingerprint) is not bytes
                    or len(proof.content_fingerprint) != 32):
                raise SurveyRoundSourceError("RESOURCE_NOT_FOUND")
            return VerifiedRoundProjectRecord(
                evidence_id=proof.evidence_id,
                project_id=proof.project_id,
                document_id=proof.document_id,
                document_version_id=proof.document_version_id,
                observed_evidence_lock_version=proof.observed_lock_version,
                content_fingerprint=proof.content_fingerprint,
                recorded_by=proof.verified_by,
            )
        except SurveyRoundSourceError:
            raise
        except Exception:
            raise SurveyRoundSourceError("ROUND_SOURCE_UNAVAILABLE") from None
