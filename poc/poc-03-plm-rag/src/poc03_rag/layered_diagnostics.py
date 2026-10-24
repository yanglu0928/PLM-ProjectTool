from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence


def document_key(chunk_id: str) -> str:
    return str(chunk_id).split("-C-", 1)[0]


def _hit(expected: set[str], ranked: Sequence[str], limit: int) -> bool:
    return bool(expected.intersection(ranked[:limit]))


def _document_hit(expected: set[str], ranked: Sequence[str], limit: int) -> bool:
    expected_documents = {document_key(item) for item in expected}
    return any(document_key(item) in expected_documents for item in ranked[:limit])


def fuse_ranked_scores(
    vector_rows: Sequence[tuple[str, float]],
    full_text_rows: Sequence[tuple[str, float]],
    *,
    vector_weight: float,
    mode: str = "normalized_score",
    rrf_k: int = 60,
) -> list[str]:
    if not 0.0 <= vector_weight <= 1.0:
        raise ValueError("vector_weight must be between 0 and 1")
    text_weight = 1.0 - vector_weight
    if mode == "normalized_score":
        vector_scores = {str(item): max(0.0, float(score)) for item, score in vector_rows}
        raw_text_scores = {
            str(item): max(0.0, float(score)) for item, score in full_text_rows
        }
        max_text_score = max(raw_text_scores.values(), default=0.0)
        text_scores = {
            item: score / max_text_score if max_text_score else 0.0
            for item, score in raw_text_scores.items()
        }
        combined = {
            item: vector_weight * vector_scores.get(item, 0.0)
            + text_weight * text_scores.get(item, 0.0)
            for item in set(vector_scores) | set(text_scores)
        }
    elif mode == "rrf":
        combined: dict[str, float] = defaultdict(float)
        for rank, (item, _) in enumerate(vector_rows, start=1):
            combined[str(item)] += vector_weight / (rrf_k + rank)
        for rank, (item, _) in enumerate(full_text_rows, start=1):
            combined[str(item)] += text_weight / (rrf_k + rank)
    else:
        raise ValueError("unsupported fusion mode")
    return sorted(combined, key=lambda item: (-combined[item], item))


def expand_ranked_neighbors(
    ranked: Sequence[str],
    *,
    document_chunks: Mapping[str, Sequence[str]],
    fused_limit: int,
    neighbor_radius: int,
) -> list[str]:
    """Expand a ranked candidate list with deterministic same-document neighbors."""
    if fused_limit < 1:
        raise ValueError("fused_limit must be positive")
    if neighbor_radius < 0:
        raise ValueError("neighbor_radius must be non-negative")
    positions = {
        str(chunk_id): (str(document_id), index)
        for document_id, chunk_ids in document_chunks.items()
        for index, chunk_id in enumerate(chunk_ids)
    }
    expanded: list[str] = []
    seen: set[str] = set()
    for raw_chunk_id in ranked[:fused_limit]:
        chunk_id = str(raw_chunk_id)
        if chunk_id not in seen:
            expanded.append(chunk_id)
            seen.add(chunk_id)
        position = positions.get(chunk_id)
        if position is None or neighbor_radius == 0:
            continue
        document_id, index = position
        siblings = [str(item) for item in document_chunks[document_id]]
        for distance in range(1, neighbor_radius + 1):
            for neighbor_index in (index - distance, index + distance):
                if 0 <= neighbor_index < len(siblings):
                    neighbor_id = siblings[neighbor_index]
                    if neighbor_id not in seen:
                        expanded.append(neighbor_id)
                        seen.add(neighbor_id)
    return expanded


def _stage_summary(
    cases: list[dict[str, Any]],
    rankings: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    exact_top5 = exact_top20 = document_top5 = document_top20 = 0
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for case in cases:
        case_id = str(case["case_id"])
        source_type = str(case["source_type"])
        expected = {str(item) for item in case["expected_relevant_chunk_ids"]}
        ranked = list(rankings.get(case_id) or [])
        exact5 = _hit(expected, ranked, 5)
        exact20 = _hit(expected, ranked, 20)
        doc5 = _document_hit(expected, ranked, 5)
        doc20 = _document_hit(expected, ranked, 20)
        exact_top5 += exact5
        exact_top20 += exact20
        document_top5 += doc5
        document_top20 += doc20
        by_source[source_type]["cases"] += 1
        by_source[source_type]["exact_top5"] += exact5
        by_source[source_type]["exact_top20"] += exact20
    count = len(cases)
    return {
        "case_count": count,
        "exact_top5_hits": exact_top5,
        "exact_top5_recall": exact_top5 / count if count else 0.0,
        "exact_top20_hits": exact_top20,
        "exact_top20_recall": exact_top20 / count if count else 0.0,
        "same_document_top5_hits": document_top5,
        "same_document_top5_recall": document_top5 / count if count else 0.0,
        "same_document_top20_hits": document_top20,
        "same_document_top20_recall": document_top20 / count if count else 0.0,
        "by_source_type": {
            source_type: dict(sorted(counts.items()))
            for source_type, counts in sorted(by_source.items())
        },
    }


def build_layered_diagnostic(
    cases: list[dict[str, Any]],
    *,
    vector_rankings: Mapping[str, Sequence[str]],
    full_text_rankings: Mapping[str, Sequence[str]],
    fusion_rankings: Mapping[str, Sequence[str]],
    reranked_rankings: Mapping[str, Sequence[str]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    stage_rankings = {
        "vector": vector_rankings,
        "full_text": full_text_rankings,
        "fusion": fusion_rankings,
        "reranker": reranked_rankings,
    }
    stages = {
        name: _stage_summary(cases, rankings)
        for name, rankings in stage_rankings.items()
    }
    bottlenecks: Counter[str] = Counter()
    classification_correct = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    case_diagnostics: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        expected = {str(item) for item in case["expected_relevant_chunk_ids"]}
        vector = list(vector_rankings.get(case_id) or [])
        full_text = list(full_text_rankings.get(case_id) or [])
        fusion = list(fusion_rankings.get(case_id) or [])
        reranked = list(reranked_rankings.get(case_id) or [])
        union20 = set(vector[:20]) | set(full_text[:20])
        if not expected.intersection(union20):
            bottleneck = "CHANNEL_RECALL_MISS"
        elif not _hit(expected, fusion, 20):
            bottleneck = "FUSION_DROPPED"
        elif not _hit(expected, reranked, 5):
            bottleneck = "RERANKER_DROPPED"
        elif not _hit(expected, fusion, 5):
            bottleneck = "RERANKER_RECOVERED"
        else:
            bottleneck = "RETRIEVAL_TOP5_OK"
        bottlenecks[bottleneck] += 1

        expected_classification = str(case["expected_classification"])
        predicted_classification = str(
            (predictions.get(case_id) or {}).get("classification") or "MISSING"
        )
        confusion[expected_classification][predicted_classification] += 1
        classification_correct += predicted_classification == expected_classification
        case_diagnostics.append(
            {
                "case_id": case_id,
                "source_type": str(case["source_type"]),
                "bottleneck": bottleneck,
                "vector_exact_top20": _hit(expected, vector, 20),
                "full_text_exact_top20": _hit(expected, full_text, 20),
                "fusion_exact_top20": _hit(expected, fusion, 20),
                "reranker_exact_top5": _hit(expected, reranked, 5),
                "reranker_same_document_top5": _document_hit(expected, reranked, 5),
                "classification_correct": predicted_classification
                == expected_classification,
            }
        )
    count = len(cases)
    return {
        "schema_version": "poc-03.layered-retrieval-diagnostic.v1",
        "status": "DIAGNOSED",
        "summary": {
            "case_count": count,
            "classification_correct_count": classification_correct,
            "classification_accuracy": classification_correct / count if count else 0.0,
            "bottleneck_counts": dict(sorted(bottlenecks.items())),
        },
        "stages": stages,
        "classification_confusion": {
            expected: dict(sorted(predicted.items()))
            for expected, predicted in sorted(confusion.items())
        },
        "case_diagnostics": case_diagnostics,
        "privacy": {
            "queries_in_report": False,
            "chunk_text_in_report": False,
            "vectors_in_report": False,
            "model_responses_in_report": False,
        },
    }


def sanitized_layered_report(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key != "case_diagnostics"}
