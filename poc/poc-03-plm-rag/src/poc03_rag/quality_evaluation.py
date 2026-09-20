from __future__ import annotations

import re
import math
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping


ALLOWED_CLASSIFICATIONS = {
    "STANDARD_SATISFIED",
    "PARTIALLY_SATISFIED",
    "NON_STANDARD",
    "INSUFFICIENT_INFORMATION",
    "NO_RELIABLE_MATCH",
    "HUMAN_CONFIRMATION_REQUIRED",
}

_GENERIC_QUERY_TERMS = {
    "关于",
    "哪些",
    "明确",
    "约定",
    "参考",
    "资料",
    "采用",
    "什么",
    "方式",
    "配置",
    "如何",
    "进行",
    "系统",
    "功能",
}


def normalize_cjk_spacing(text: str) -> str:
    """Remove OCR whitespace inserted between adjacent CJK characters."""
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", str(text))


def lexical_terms(text: str, *, limit: int = 32) -> list[str]:
    if limit < 1:
        raise ValueError("limit must be positive")
    text = normalize_cjk_spacing(text)
    quoted = re.findall(r"[“\"]([^”\"]+)[”\"]", text)
    source = " ".join(quoted) if quoted else text
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", source.lower()):
        if len(token) >= 2:
            terms.append(token)
    for run in re.findall(r"[\u4e00-\u9fff]+", source):
        if len(run) == 1:
            terms.append(run)
            continue
        for size in (2, 3):
            terms.extend(run[index : index + size] for index in range(len(run) - size + 1))
    unique = []
    seen = set()
    for term in terms:
        if term in _GENERIC_QUERY_TERMS or term in seen:
            continue
        seen.add(term)
        unique.append(term)
        if len(unique) >= limit:
            break
    return unique


def searchable_text(text: str) -> str:
    text = normalize_cjk_spacing(text)
    terms: list[str] = []
    terms.extend(re.findall(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", text.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) == 1:
            terms.append(run)
        else:
            terms.extend(run[index : index + 2] for index in range(len(run) - 1))
            terms.extend(run[index : index + 3] for index in range(len(run) - 2))
    return " ".join(terms)


def rank_lexical_overlap(
    query: str,
    candidates: Mapping[str, str],
    *,
    limit: int = 5,
) -> list[str]:
    """Rank text by deterministic CJK-aware term coverage with corpus IDF."""
    if limit < 1:
        raise ValueError("limit must be positive")
    terms = lexical_terms(query, limit=64)
    normalized = {
        str(candidate_id): normalize_cjk_spacing(text).lower()
        for candidate_id, text in candidates.items()
    }
    document_frequency = {
        term: sum(term in text for text in normalized.values()) for term in terms
    }
    count = len(normalized)
    scores = {
        candidate_id: sum(
            len(term) * math.log((count + 1) / (document_frequency[term] + 1))
            for term in terms
            if term in text
        )
        for candidate_id, text in normalized.items()
    }
    return sorted(scores, key=lambda item: (-scores[item], item))[:limit]


def merge_hybrid_and_lexical_candidates(
    vector_rows: Iterable[tuple[str, float]],
    full_text_rows: Iterable[tuple[str, float]],
    lexical_ranked_ids: Iterable[str],
    *,
    channel_limit: int = 20,
    vector_weight: float = 0.6,
) -> list[str]:
    """Merge three source-filtered recall channels before external reranking.

    The locked 0.6/0.4 weighting still orders the vector/full-text union. The
    lexical IDF channel expands recall only; it does not replace or reweight the
    existing hybrid score. Duplicate chunk IDs retain their earliest position.
    """
    if channel_limit < 1:
        raise ValueError("channel_limit must be positive")
    if not 0.0 <= vector_weight <= 1.0:
        raise ValueError("vector_weight must be between 0 and 1")
    vector = [(str(item), max(0.0, float(score))) for item, score in vector_rows][
        :channel_limit
    ]
    full_text = [
        (str(item), max(0.0, float(score))) for item, score in full_text_rows
    ][:channel_limit]
    vector_scores = dict(vector)
    raw_text_scores = dict(full_text)
    max_text_score = max(raw_text_scores.values(), default=0.0)
    text_scores = {
        chunk_id: score / max_text_score if max_text_score else 0.0
        for chunk_id, score in raw_text_scores.items()
    }
    combined = {
        chunk_id: vector_weight * vector_scores.get(chunk_id, 0.0)
        + (1.0 - vector_weight) * text_scores.get(chunk_id, 0.0)
        for chunk_id in set(vector_scores) | set(text_scores)
    }
    hybrid_ranked = sorted(
        combined, key=lambda chunk_id: (-combined[chunk_id], chunk_id)
    )
    merged: list[str] = []
    seen: set[str] = set()
    for chunk_id in [*hybrid_ranked, *list(lexical_ranked_ids)[:channel_limit]]:
        value = str(chunk_id)
        if value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


def merge_reranked_with_protected_lexical(
    reranked_ids: Iterable[str],
    lexical_ranked_ids: Iterable[str],
    *,
    top_k: int = 5,
    protected_lexical_count: int = 4,
) -> list[str]:
    """Keep one semantic winner while protecting exact/OCR-sensitive evidence.

    The policy is query-only and label-agnostic: the first external reranker
    result is retained, followed by the highest deterministic lexical results.
    Remaining slots are filled from the two rankings without duplicates.
    """
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not 0 <= protected_lexical_count <= top_k:
        raise ValueError("protected_lexical_count must be between zero and top_k")
    reranked = [str(value) for value in reranked_ids]
    lexical = [str(value) for value in lexical_ranked_ids]
    protected = lexical[:protected_lexical_count]
    semantic_count = top_k - protected_lexical_count
    ordered = [*reranked[:semantic_count], *protected, *reranked, *lexical]
    merged: list[str] = []
    seen: set[str] = set()
    for value in ordered:
        if value and value not in seen:
            seen.add(value)
            merged.append(value)
            if len(merged) == top_k:
                break
    return merged


def tsquery_or(terms: Iterable[str]) -> str:
    safe = []
    for term in terms:
        normalized = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff.+-]", "", str(term))
        if normalized:
            safe.append(normalized)
    return " | ".join(dict.fromkeys(safe))


def parse_plain_prediction(
    text: str, *, valid_chunk_ids: Iterable[str]
) -> dict[str, Any]:
    """Parse one constrained final marker without accepting invented IDs."""
    match = re.fullmatch(r"\s*([A-Z_]+)\s*\|\s*([^\s|]+)\s*", text)
    if match is None:
        markers = re.findall(
            r"(?m)^\s*FINAL:\s*([A-Z_]+)\s*\|\s*([^\s|]+)\s*$", text
        )
        if len(markers) != 1:
            raise ValueError("prediction must contain exactly one constrained final marker")
        classification, chunk_id = markers[0]
    else:
        classification, chunk_id = match.groups()
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError("prediction classification is not allowed")
    allowed_ids = {str(value) for value in valid_chunk_ids}
    if chunk_id not in allowed_ids:
        raise ValueError("prediction cited a chunk outside the supplied contexts")
    return {
        "classification": classification,
        "citation_chunk_ids": [chunk_id],
    }


def evaluate_retrieval_quality(
    cases: list[dict[str, Any]],
    retrievals: dict[str, list[str]],
    *,
    reranker_live_count: int,
    gin_index_used: bool,
    hnsw_index_used: bool,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("cases must not be empty")
    recall_hits = same_document_hits = 0
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for case in cases:
        case_id = str(case["case_id"])
        retrieved = list(retrievals.get(case_id) or [])[:5]
        expected = {str(value) for value in case["expected_relevant_chunk_ids"]}
        expected_documents = {value.rsplit("-C-", 1)[0] for value in expected}
        exact_hit = bool(expected.intersection(retrieved))
        same_document_hit = bool(
            expected_documents.intersection(
                value.rsplit("-C-", 1)[0] for value in retrieved
            )
        )
        recall_hits += exact_hit
        same_document_hits += same_document_hit
        source_counts = by_source[str(case.get("source_type") or "UNKNOWN")]
        source_counts["case_count"] += 1
        source_counts["exact_chunk_retrieval_hits"] += exact_hit
        source_counts["same_document_retrieval_hits"] += same_document_hit
    count = len(cases)
    recall = recall_hits / count
    checks = {
        "top5_recall_at_least_95_percent": recall >= 0.95,
        "all_reranker_calls_live": reranker_live_count == count,
        "gin_index_used": gin_index_used,
        "hnsw_index_used": hnsw_index_used,
    }
    return {
        "schema_version": "poc-03.live-retrieval-result.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "summary": {
            "case_count": count,
            "top_k": 5,
            "top5_recall_hits": recall_hits,
            "top5_recall": recall,
            "same_document_top5_hits": same_document_hits,
            "same_document_top5_recall": same_document_hits / count,
            "reranker_live_count": reranker_live_count,
        },
        "thresholds": {"top5_recall": 0.95},
        "checks": checks,
        "diagnostics": {
            "by_source_type": {
                source: dict(sorted(values.items()))
                for source, values in sorted(by_source.items())
            }
        },
        "privacy": {
            "queries_committed": False,
            "document_text_committed": False,
            "vectors_committed": False,
            "model_responses_committed": False,
            "case_level_results_committed": False,
            "api_keys_committed": False,
        },
    }


def evaluate_quality(
    cases: list[dict[str, Any]],
    retrievals: dict[str, list[str]],
    predictions: dict[str, dict[str, Any]],
    *,
    reranker_live_count: int,
    gin_index_used: bool,
    hnsw_index_used: bool,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("cases must not be empty")
    recall_hits = 0
    classification_hits = 0
    citation_hits = 0
    invalid_citation_case_count = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    expected_distribution: Counter[str] = Counter()
    predicted_distribution: Counter[str] = Counter()
    conditional = Counter()
    missing_prediction_count = 0
    for case in cases:
        case_id = str(case["case_id"])
        retrieved = list(retrievals.get(case_id) or [])[:5]
        expected_chunks = {str(value) for value in case["expected_relevant_chunk_ids"]}
        expected_documents = {value.rsplit("-C-", 1)[0] for value in expected_chunks}
        retrieval_hit = bool(expected_chunks.intersection(retrieved))
        same_document_hit = bool(
            expected_documents.intersection(
                value.rsplit("-C-", 1)[0] for value in retrieved
            )
        )
        recall_hits += retrieval_hit
        source = str(case.get("source_type") or "UNKNOWN")
        source_counts = by_source[source]
        source_counts["case_count"] += 1
        source_counts["exact_chunk_retrieval_hits"] += retrieval_hit
        source_counts["same_document_retrieval_hits"] += same_document_hit

        prediction = predictions.get(case_id)
        expected_classification = str(case["expected_classification"])
        expected_distribution[expected_classification] += 1
        if prediction is None:
            missing_prediction_count += 1
            confusion[expected_classification]["MISSING"] += 1
            conditional["retrieval_hit_cases" if retrieval_hit else "retrieval_miss_cases"] += 1
            continue
        actual_classification = str(prediction.get("classification") or "")
        predicted_distribution[actual_classification or "MISSING"] += 1
        confusion[expected_classification][actual_classification or "MISSING"] += 1
        classification_hit = actual_classification == expected_classification
        classification_hits += classification_hit
        source_counts["classification_hits"] += classification_hit
        conditional["retrieval_hit_cases" if retrieval_hit else "retrieval_miss_cases"] += 1
        if classification_hit:
            conditional[
                "classification_hits_with_retrieval_hit"
                if retrieval_hit
                else "classification_hits_with_retrieval_miss"
            ] += 1

        predicted_citations = {
            str(value) for value in prediction.get("citation_chunk_ids") or []
        }
        citation_is_valid = bool(predicted_citations) and predicted_citations.issubset(
            set(retrieved)
        )
        invalid_citation_case_count += not citation_is_valid
        citation_hits += citation_is_valid and bool(
            expected_chunks.intersection(predicted_citations)
        )
        source_counts["exact_chunk_citation_hits"] += bool(
            expected_chunks.intersection(predicted_citations)
        )
        source_counts["same_document_citation_hits"] += bool(
            expected_documents.intersection(
                value.rsplit("-C-", 1)[0] for value in predicted_citations
            )
        )

    count = len(cases)
    top5_recall = recall_hits / count
    classification_accuracy = classification_hits / count
    citation_accuracy = citation_hits / count
    thresholds = {
        "top5_recall": 0.95,
        "classification_accuracy": 0.90,
        "citation_accuracy": 0.98,
    }
    checks = {
        "top5_recall_at_least_95_percent": top5_recall >= thresholds["top5_recall"],
        "classification_accuracy_at_least_90_percent": classification_accuracy
        >= thresholds["classification_accuracy"],
        "citation_accuracy_at_least_98_percent": citation_accuracy
        >= thresholds["citation_accuracy"],
        "all_reranker_calls_live": reranker_live_count == count,
        "gin_index_used": gin_index_used,
        "hnsw_index_used": hnsw_index_used,
        "all_predictions_present": missing_prediction_count == 0,
    }
    return {
        "schema_version": "poc-03.live-quality-result.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "summary": {
            "case_count": count,
            "top_k": 5,
            "top5_recall_hits": recall_hits,
            "top5_recall": top5_recall,
            "classification_correct_count": classification_hits,
            "classification_accuracy": classification_accuracy,
            "citation_correct_count": citation_hits,
            "citation_accuracy": citation_accuracy,
            "invalid_citation_case_count": invalid_citation_case_count,
            "missing_prediction_count": missing_prediction_count,
            "reranker_live_count": reranker_live_count,
        },
        "thresholds": thresholds,
        "checks": checks,
        "classification_confusion": {
            expected: dict(sorted(actual.items()))
            for expected, actual in sorted(confusion.items())
        },
        "diagnostics": {
            "expected_classification_distribution": dict(
                sorted(expected_distribution.items())
            ),
            "predicted_classification_distribution": dict(
                sorted(predicted_distribution.items())
            ),
            "classification_conditioned_on_retrieval": dict(sorted(conditional.items())),
            "by_source_type": {
                source: dict(sorted(values.items()))
                for source, values in sorted(by_source.items())
            },
        },
        "privacy": {
            "queries_committed": False,
            "document_text_committed": False,
            "vectors_committed": False,
            "model_responses_committed": False,
            "case_level_results_committed": False,
            "api_keys_committed": False,
        },
    }
