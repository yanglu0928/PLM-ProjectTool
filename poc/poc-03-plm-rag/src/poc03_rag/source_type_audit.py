from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


REQUIRED_SOURCE_TYPES = {
    "STANDARD_CAPABILITY",
    "CONTRACT",
    "TECHNICAL_AGREEMENT",
    "SURVEY",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def classify_document_source(*, source_corpus: str, file_name: str) -> dict[str, str | None]:
    corpus = _text(source_corpus).upper()
    normalized_name = "".join(_text(file_name).split()).lower()
    if corpus in {"STANDARD_CAPABILITY", "SURVEY"}:
        return {
            "eligibility": "ELIGIBLE",
            "proposed_source_type": corpus,
            "reason": "USER_DESIGNATED_SOURCE_LIBRARY",
        }
    if corpus != "CONTRACT":
        return {
            "eligibility": "INELIGIBLE",
            "proposed_source_type": None,
            "reason": "SOURCE_CORPUS_OUTSIDE_LOCKED_GOLDEN_TYPES",
        }

    has_technical_agreement = "技术协议" in normalized_name
    has_contract = "合同" in normalized_name
    if has_technical_agreement and not has_contract:
        return {
            "eligibility": "ELIGIBLE",
            "proposed_source_type": "TECHNICAL_AGREEMENT",
            "reason": "EXPLICIT_DOCUMENT_TITLE",
        }
    if has_contract and not has_technical_agreement:
        return {
            "eligibility": "ELIGIBLE",
            "proposed_source_type": "CONTRACT",
            "reason": "EXPLICIT_DOCUMENT_TITLE",
        }
    return {
        "eligibility": "AMBIGUOUS",
        "proposed_source_type": None,
        "reason": "DOCUMENT_TITLE_NOT_DETERMINISTIC",
    }


def audit_candidate_source_types(
    candidates: Iterable[dict[str, Any]],
    review_rows: Iterable[dict[str, Any]],
    documents: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_by_id = {_text(row.get("candidate_id")): row for row in review_rows}
    document_by_id = {_text(item.get("document_id")): item for item in documents}
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = _text(candidate.get("candidate_id"))
        citations = candidate.get("expected_citations") or []
        document_id = _text(citations[0].get("document_id")) if len(citations) == 1 else ""
        if candidate_id not in review_by_id:
            raise ValueError(f"candidate has no review row: {candidate_id}")
        if document_id not in document_by_id:
            raise ValueError(f"candidate has no document descriptor: {candidate_id}")
        review = review_by_id[candidate_id]
        descriptor = document_by_id[document_id]
        classification = classify_document_source(
            source_corpus=_text(candidate.get("source_corpus")),
            file_name=_text(descriptor.get("file_name")),
        )
        proposed = classification["proposed_source_type"]
        existing = _text(review.get("source_type")).upper()
        eligibility = classification["eligibility"]
        if eligibility == "ELIGIBLE" and existing == proposed:
            audit_status = "VERIFIED"
        elif eligibility == "ELIGIBLE":
            audit_status = "CORRECTION_REQUIRED"
        elif eligibility == "AMBIGUOUS":
            audit_status = "HUMAN_CLASSIFICATION_REQUIRED"
        else:
            audit_status = "EXCLUDED_UNSUPPORTED_SOURCE_TYPE"
        results.append(
            {
                "candidate_id": candidate_id,
                "document_id": document_id,
                "existing_source_type": existing or None,
                "proposed_source_type": proposed,
                "eligibility": eligibility,
                "audit_status": audit_status,
                "reason": classification["reason"],
            }
        )
    if len(results) != len(review_by_id):
        raise ValueError("candidate and review row counts do not match")
    return results


def build_sanitized_source_type_report(
    rows: Iterable[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    entries = list(rows)
    proposed_counts = Counter(
        _text(row.get("proposed_source_type"))
        for row in entries
        if row.get("proposed_source_type")
    )
    missing_source_types = sorted(REQUIRED_SOURCE_TYPES - set(proposed_counts))
    status_counts = Counter(_text(row.get("audit_status")) for row in entries)
    eligible_count = sum(row.get("eligibility") == "ELIGIBLE" for row in entries)
    minimum_case_gap = max(0, 100 - eligible_count)
    return {
        "schema_version": "poc-03.source-type-audit-result.v1",
        "generated_at": generated_at,
        "status": "PASS" if entries else "FAIL",
        "p03_a02_status": (
            "BLOCKED_MISSING_SOURCE_CORPORA"
            if missing_source_types or minimum_case_gap
            else "READY_FOR_HUMAN_REVIEW"
        ),
        "summary": {
            "candidate_count": len(entries),
            "eligible_candidate_count": eligible_count,
            "minimum_case_count_gap": minimum_case_gap,
            "proposed_source_type_counts": dict(sorted(proposed_counts.items())),
            "audit_status_counts": dict(sorted(status_counts.items())),
            "missing_required_source_types": missing_source_types,
        },
        "privacy": {
            "source_file_names_committed": False,
            "source_content_committed": False,
            "reviewer_names_committed": False,
            "local_mapping_committed": False,
        },
        "conclusion": (
            "Existing evidence can support contract and technical-agreement cases only; "
            "standard-capability and survey source corpora are still required."
        ),
    }
