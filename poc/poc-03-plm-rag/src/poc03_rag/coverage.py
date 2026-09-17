from __future__ import annotations

from collections import Counter
from typing import Any


REQUIRED_SOURCE_TYPES = {
    "STANDARD_CAPABILITY",
    "CONTRACT",
    "TECHNICAL_AGREEMENT",
    "SURVEY",
}

REQUIRED_CLASSIFICATIONS = {
    "STANDARD_SATISFIED",
    "PARTIALLY_SATISFIED",
    "NON_STANDARD",
    "INSUFFICIENT_INFORMATION",
    "NO_RELIABLE_MATCH",
    "HUMAN_CONFIRMATION_REQUIRED",
}


def audit_golden_dataset_coverage(dataset: dict[str, Any]) -> dict[str, Any]:
    cases = list(dataset.get("cases") or [])
    source_type_counts = Counter(str(case.get("source_type") or "") for case in cases)
    classification_counts = Counter(
        str(case.get("expected_classification") or "") for case in cases
    )
    queries = [str(case.get("query") or "").strip() for case in cases]
    document_ids = {
        str(citation.get("document_id") or "")
        for case in cases
        for citation in case.get("expected_citations") or []
    }
    chunk_ids = {
        str(chunk_id)
        for case in cases
        for chunk_id in case.get("expected_relevant_chunk_ids") or []
    }
    project_ids = {
        str(case.get("project_id"))
        for case in cases
        if case.get("project_id") is not None
    }
    missing_source_types = sorted(REQUIRED_SOURCE_TYPES - set(source_type_counts))
    missing_classifications = sorted(
        REQUIRED_CLASSIFICATIONS - set(classification_counts)
    )
    duplicate_query_count = len(queries) - len(set(queries))
    checks = {
        "case_count_100_to_200": 100 <= len(cases) <= 200,
        "distinct_query_per_case": bool(cases) and duplicate_query_count == 0,
        "all_source_types_present": not missing_source_types,
        "all_classifications_present": not missing_classifications,
    }
    return {
        "schema_version": "poc-03.golden-coverage-result.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "summary": {
            "case_count": len(cases),
            "unique_query_count": len(set(queries)),
            "duplicate_query_count": duplicate_query_count,
            "unique_document_count": len(document_ids - {""}),
            "unique_chunk_count": len(chunk_ids - {""}),
            "unique_project_count": len(project_ids),
            "source_type_counts": dict(sorted(source_type_counts.items())),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "checks": checks,
        "missing_source_types": missing_source_types,
        "missing_classifications": missing_classifications,
        "privacy": {
            "queries_committed": False,
            "answer_terms_committed": False,
            "reviewer_names_committed": False,
            "dataset_committed": False,
        },
    }
