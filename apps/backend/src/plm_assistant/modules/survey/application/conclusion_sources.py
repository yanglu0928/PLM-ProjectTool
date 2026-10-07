"""Typed, caller-transaction source proofs consumed by SurveyConclusion."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, VerifiedProjectEvidence,
)


class SurveyConclusionSourceError(RuntimeError):
    def __init__(self, code: str = "SURVEY_CONCLUSION_SOURCE_INVALID") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ConclusionResponseEvidenceProof:
    evidence_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ConclusionResponseProof:
    response_id: uuid.UUID
    answer_id: uuid.UUID
    assignment_id: uuid.UUID
    round_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    department_id: uuid.UUID
    question_row_id: uuid.UUID
    response_source: str
    answer_fingerprint: bytes = field(repr=False)
    evidence_ids: tuple[uuid.UUID, ...] = ()
    evidence: tuple[ConclusionResponseEvidenceProof, ...] = ()


@dataclass(frozen=True, slots=True)
class ConclusionProjectRecordProof:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    verified_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class ConclusionProjectRecordQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    evidence_id: uuid.UUID


class ConclusionResponseOwner(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              survey_id: uuid.UUID, round_refs: tuple[uuid.UUID, ...],
              response_id: uuid.UUID) -> ConclusionResponseProof | None: ...


class ProjectEvidenceOwner(Protocol):
    def prove(self, transaction: object, query: EvidenceFixedProjectQuery,
              evidence_id: uuid.UUID) -> VerifiedProjectEvidence: ...


class SurveyConclusionProjectRecordProofService:
    def __init__(self, *, evidence: ProjectEvidenceOwner,
                 allowed_verified_roles: frozenset[str] | None = None) -> None:
        roles = (frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
                 if allowed_verified_roles is None else allowed_verified_roles)
        if (evidence is None or type(roles) is not frozenset or not roles
                or not roles.issubset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                    "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
                })):
            raise ValueError("PROJECT_RECORD Evidence Owner required")
        self._evidence = evidence
        self._allowed_verified_roles = roles

    def prove(self, transaction: object,
              query: ConclusionProjectRecordQuery) -> ConclusionProjectRecordProof:
        if (transaction is None or type(query) is not ConclusionProjectRecordQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    query.trace_id, query.project_id, query.evidence_id,
                ))):
            raise SurveyConclusionSourceError()
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
                    or proof.scope != "PROJECT" or proof.observed_state != "ELIGIBLE"
                    or proof.document_category != "PROJECT_RECORD"
                    or proof.verified_project_role
                    not in self._allowed_verified_roles
                    or type(proof.verified_by) is not uuid.UUID
                    or proof.verified_by.int == 0
                    or type(proof.observed_lock_version) is not int
                    or not 0 <= proof.observed_lock_version < 2**63
                    or type(proof.content_fingerprint) is not bytes
                    or len(proof.content_fingerprint) != 32):
                raise SurveyConclusionSourceError()
            return ConclusionProjectRecordProof(
                proof.evidence_id, proof.project_id, proof.document_id,
                proof.document_version_id, proof.observed_lock_version,
                proof.content_fingerprint, proof.verified_by,
            )
        except SurveyConclusionSourceError:
            raise
        except Exception:
            raise SurveyConclusionSourceError() from None
