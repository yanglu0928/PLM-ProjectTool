"""Deterministic FTS-only final ranking and score plan."""

from __future__ import annotations

from dataclasses import dataclass

from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalPreparationError,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidate,
    ProjectFTSCandidatePlan,
)


_POLICY = "fts.project.v1"


@dataclass(frozen=True, slots=True)
class RetrievalScorePartPlan:
    score_kind: str
    score_ordinal: int
    raw_score_micros: int
    normalized_score_micros: int
    weight_micros: int
    weighted_score_micros: int
    score_policy_ref: str

    def __post_init__(self) -> None:
        if (self.score_kind not in {"FTS", "FINAL"}
                or type(self.score_ordinal) is not int
                or not 0 <= self.score_ordinal <= 31
                or type(self.raw_score_micros) is not int
                or not 0 <= self.raw_score_micros <= 1_000_000_000
                or type(self.normalized_score_micros) is not int
                or not 0 <= self.normalized_score_micros <= 1_000_000
                or self.weight_micros != 1_000_000
                or self.weighted_score_micros != self.raw_score_micros
                or self.score_policy_ref != _POLICY):
            raise RAGRetrievalPreparationError("RAG_RETRIEVAL_MERGE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class RankedFTSCandidate:
    final_ordinal: int
    candidate: ProjectFTSCandidate
    final_score_micros: int
    score_parts: tuple[RetrievalScorePartPlan, RetrievalScorePartPlan]

    def __post_init__(self) -> None:
        if (type(self.final_ordinal) is not int or not 0 <= self.final_ordinal < 100
                or type(self.candidate) is not ProjectFTSCandidate
                or self.final_score_micros != self.candidate.raw_score_micros
                or type(self.score_parts) is not tuple or len(self.score_parts) != 2
                or tuple(part.score_kind for part in self.score_parts)
                != ("FTS", "FINAL")):
            raise RAGRetrievalPreparationError("RAG_RETRIEVAL_MERGE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class FTSRetrievalMergePlan:
    retrieval_policy_ref: str
    rerank_state: str
    egress_state: str
    degraded: bool
    quality_flags: tuple[str, ...]
    candidates: tuple[RankedFTSCandidate, ...]

    def __post_init__(self) -> None:
        if (self.retrieval_policy_ref != _POLICY
                or self.rerank_state != "NOT_APPLICABLE"
                or self.egress_state != "NOT_APPLICABLE"
                or self.degraded is not False
                or self.quality_flags not in ((), ("CANDIDATE_SHORTFALL",))
                or not 1 <= len(self.candidates) <= 100
                or tuple(item.final_ordinal for item in self.candidates)
                != tuple(range(len(self.candidates)))):
            raise RAGRetrievalPreparationError("RAG_RETRIEVAL_MERGE_UNAVAILABLE")


class FTSRetrievalMergePlanner:
    def plan(self, candidates: ProjectFTSCandidatePlan, *, top_k: int
             ) -> FTSRetrievalMergePlan:
        if (type(candidates) is not ProjectFTSCandidatePlan
                or type(top_k) is not int or not 1 <= top_k <= 100):
            raise RAGRetrievalPreparationError("RAG_RETRIEVAL_MERGE_UNAVAILABLE")
        candidates.__post_init__()
        if not candidates.candidates:
            raise RAGRetrievalPreparationError("RAG_NO_AUTHORIZED_CANDIDATES")
        ordered = sorted(candidates.candidates, key=lambda item: (
            -item.raw_score_micros, item.candidate_ordinal, item.chunk_id.int,
        ))[:top_k]
        ranked = []
        for ordinal, candidate in enumerate(ordered):
            normalized = min(candidate.raw_score_micros, 1_000_000)
            parts = tuple(RetrievalScorePartPlan(
                kind, part_ordinal, candidate.raw_score_micros,
                normalized, 1_000_000, candidate.raw_score_micros, _POLICY,
            ) for part_ordinal, kind in enumerate(("FTS", "FINAL")))
            ranked.append(RankedFTSCandidate(
                ordinal, candidate, candidate.raw_score_micros, parts,
            ))
        flags = ("CANDIDATE_SHORTFALL",) if len(ranked) < top_k else ()
        plan = FTSRetrievalMergePlan(
            _POLICY, "NOT_APPLICABLE", "NOT_APPLICABLE", False,
            flags, tuple(ranked),
        )
        plan.__post_init__()
        return plan
