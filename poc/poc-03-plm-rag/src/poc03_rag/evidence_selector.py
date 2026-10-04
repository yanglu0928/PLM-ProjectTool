from __future__ import annotations

from typing import Any, Mapping, Sequence

from .quality_evaluation import lexical_terms, normalize_cjk_spacing


def rank_evidence_support(
    query: str,
    candidate_chunk_ids: Sequence[str],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    project_id: str,
) -> list[dict[str, Any]]:
    """Rank supplied evidence by query support without Golden Dataset fields.

    Retrieval position is only the final tie-breaker. This prevents the former
    behavior where the first candidate was effectively treated as the answer.
    """
    if not str(query).strip():
        raise ValueError("query is required")
    if not str(project_id).strip():
        raise ValueError("project_id is required")
    if not candidate_chunk_ids:
        raise ValueError("at least one candidate chunk is required")

    terms = lexical_terms(str(query), limit=64)
    total_weight = sum(len(term) for term in terms) or 1
    scored: list[dict[str, Any]] = []
    seen: set[str] = set()
    for original_rank, raw_chunk_id in enumerate(candidate_chunk_ids, start=1):
        chunk_id = str(raw_chunk_id)
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            raise ValueError(f"unknown evidence chunk_id: {chunk_id}")
        if str(chunk.get("scope") or "") != "PROJECT":
            raise ValueError("evidence chunk must use PROJECT scope")
        if str(chunk.get("project_id") or "") != str(project_id):
            raise ValueError("evidence chunk belongs to another ProjectId")
        text = normalize_cjk_spacing(str(chunk.get("text") or "")).lower()
        if not text:
            raise ValueError("evidence chunk text must not be empty")
        matched_terms = [term for term in terms if term in text]
        matched_weight = sum(len(term) for term in matched_terms)
        scored.append(
            {
                "chunk_id": chunk_id,
                "source_corpus": str(chunk.get("source_corpus") or ""),
                "original_rank": original_rank,
                "matched_term_count": len(matched_terms),
                "query_term_count": len(terms),
                "support_score": round(matched_weight / total_weight, 6),
            }
        )
    return sorted(
        scored,
        key=lambda item: (
            -float(item["support_score"]),
            -int(item["matched_term_count"]),
            int(item["original_rank"]),
            str(item["chunk_id"]),
        ),
    )


def select_primary_evidence(
    query: str,
    candidate_chunk_ids: Sequence[str],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    project_id: str,
) -> str:
    return str(
        rank_evidence_support(
            query,
            candidate_chunk_ids,
            chunks_by_id,
            project_id=project_id,
        )[0]["chunk_id"]
    )
