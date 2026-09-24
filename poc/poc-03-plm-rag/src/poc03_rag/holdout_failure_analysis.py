from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from .quality_evaluation import normalize_cjk_spacing


def _document_key(chunk_id: str) -> str:
    return str(chunk_id).split("-C-", 1)[0]


def _rank_of_any(ranked: Sequence[str], expected: set[str]) -> int:
    for index, chunk_id in enumerate(ranked, start=1):
        if str(chunk_id) in expected:
            return index
    return 0


def _term_coverage(
    expected_terms: Sequence[str],
    cited_chunk_id: str,
    chunks_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[int, int]:
    terms = [
        normalize_cjk_spacing(str(term)).strip().lower()
        for term in expected_terms
        if str(term).strip()
    ]
    chunk = chunks_by_id.get(cited_chunk_id) or {}
    text = normalize_cjk_spacing(str(chunk.get("text") or "")).lower()
    return sum(term in text for term in terms), len(terms)


def analyze_holdout_failures(
    cases: Sequence[Mapping[str, Any]],
    retrievals: Mapping[str, Sequence[str]],
    predictions: Mapping[str, Mapping[str, Any]],
    *,
    chunks_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("cases must not be empty")

    chunks = chunks_by_id or {}
    classification_by_source: dict[str, Counter[str]] = defaultdict(Counter)
    classification_by_expected: dict[str, Counter[str]] = defaultdict(Counter)
    citation_rank_distribution: Counter[str] = Counter()
    expected_rank_distribution: Counter[str] = Counter()
    citation_by_expected_rank: dict[str, Counter[str]] = defaultdict(Counter)
    quadrants: Counter[str] = Counter()
    case_diagnostics: list[dict[str, Any]] = []
    citation_miss_count = 0
    citation_miss_same_document_count = 0
    citation_miss_full_term_coverage_count = 0
    citation_miss_partial_term_coverage_count = 0
    classification_miss_count = 0

    for case in cases:
        case_id = str(case["case_id"])
        ranked = [str(item) for item in retrievals.get(case_id) or []]
        prediction = predictions.get(case_id) or {}
        expected_chunks = {
            str(item) for item in case.get("expected_relevant_chunk_ids") or []
        }
        predicted_citations = [
            str(item) for item in prediction.get("citation_chunk_ids") or []
        ]
        cited_chunk_id = predicted_citations[0] if predicted_citations else ""
        expected_rank = _rank_of_any(ranked, expected_chunks)
        citation_rank = (
            ranked.index(cited_chunk_id) + 1 if cited_chunk_id in ranked else 0
        )
        expected_classification = str(case["expected_classification"])
        predicted_classification = str(
            prediction.get("classification") or "MISSING"
        )
        classification_ok = predicted_classification == expected_classification
        citation_ok = cited_chunk_id in expected_chunks
        expected_documents = {_document_key(item) for item in expected_chunks}
        citation_same_document = bool(cited_chunk_id) and (
            _document_key(cited_chunk_id) in expected_documents
        )
        matched_term_count, expected_term_count = _term_coverage(
            case.get("expected_answer_terms") or [], cited_chunk_id, chunks
        )
        full_term_coverage = bool(expected_term_count) and (
            matched_term_count == expected_term_count
        )
        partial_term_coverage = matched_term_count > 0 and not full_term_coverage

        source = str(case.get("source_type") or "UNKNOWN")
        source_counts = classification_by_source[source]
        source_counts["cases"] += 1
        source_counts["classification_hits"] += classification_ok
        source_counts["citation_hits"] += citation_ok
        source_counts["retrieval_hits"] += expected_rank > 0

        expected_counts = classification_by_expected[expected_classification]
        expected_counts["cases"] += 1
        expected_counts["classification_hits"] += classification_ok

        expected_rank_distribution[str(expected_rank)] += 1
        citation_rank_distribution[str(citation_rank)] += 1
        citation_by_expected_rank[str(expected_rank)]["cases"] += 1
        citation_by_expected_rank[str(expected_rank)]["citation_hits"] += citation_ok
        quadrants[
            f"classification_{'hit' if classification_ok else 'miss'}__"
            f"citation_{'hit' if citation_ok else 'miss'}"
        ] += 1

        classification_miss_count += not classification_ok
        if not citation_ok:
            citation_miss_count += 1
            citation_miss_same_document_count += citation_same_document
            citation_miss_full_term_coverage_count += full_term_coverage
            citation_miss_partial_term_coverage_count += partial_term_coverage

        case_diagnostics.append(
            {
                "case_id": case_id,
                "source_type": source,
                "expected_classification": expected_classification,
                "predicted_classification": predicted_classification,
                "classification_ok": classification_ok,
                "retrieval_ok": expected_rank > 0,
                "expected_chunk_rank": expected_rank,
                "citation_rank": citation_rank,
                "citation_ok": citation_ok,
                "citation_same_document": citation_same_document,
                "expected_answer_term_count": expected_term_count,
                "cited_chunk_matched_term_count": matched_term_count,
                "cited_chunk_full_term_coverage": full_term_coverage,
            }
        )

    count = len(cases)
    requirement_sources = {"CONTRACT", "SURVEY", "TECHNICAL_AGREEMENT"}
    requirement_cases = [
        item for item in case_diagnostics if item["source_type"] in requirement_sources
    ]
    return {
        "schema_version": "poc-03.holdout-failure-analysis.v1",
        "status": "DIAGNOSED",
        "summary": {
            "case_count": count,
            "classification_miss_count": classification_miss_count,
            "citation_miss_count": citation_miss_count,
            "retrieval_miss_count": sum(
                not item["retrieval_ok"] for item in case_diagnostics
            ),
            "requirement_source_case_count": len(requirement_cases),
            "requirement_source_classification_hit_count": sum(
                item["classification_ok"] for item in requirement_cases
            ),
            "rank1_citation_count": citation_rank_distribution["1"],
            "citation_miss_same_document_count": citation_miss_same_document_count,
            "citation_miss_full_expected_term_coverage_count": (
                citation_miss_full_term_coverage_count
            ),
            "citation_miss_partial_expected_term_coverage_count": (
                citation_miss_partial_term_coverage_count
            ),
        },
        "classification_by_source_type": {
            key: dict(sorted(value.items()))
            for key, value in sorted(classification_by_source.items())
        },
        "classification_by_expected_label": {
            key: dict(sorted(value.items()))
            for key, value in sorted(classification_by_expected.items())
        },
        "classification_citation_quadrants": dict(sorted(quadrants.items())),
        "expected_chunk_rank_distribution": dict(
            sorted(expected_rank_distribution.items(), key=lambda item: int(item[0]))
        ),
        "citation_rank_distribution": dict(
            sorted(citation_rank_distribution.items(), key=lambda item: int(item[0]))
        ),
        "citation_by_expected_chunk_rank": {
            key: dict(sorted(value.items()))
            for key, value in sorted(
                citation_by_expected_rank.items(), key=lambda item: int(item[0])
            )
        },
        "case_diagnostics": case_diagnostics,
        "privacy": {
            "queries_in_report": False,
            "chunk_text_in_report": False,
            "vectors_in_report": False,
            "model_responses_in_report": False,
            "reviewer_identity_in_report": False,
        },
    }


def sanitized_failure_analysis(report: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key != "case_diagnostics"}
