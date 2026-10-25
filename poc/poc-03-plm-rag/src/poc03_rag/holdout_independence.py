"""Local, content-free overlap preflight for a new Gate 3 holdout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _query_key(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _keys(cases: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {
        "query": set(),
        "chunk_id": set(),
        "source_locator": set(),
        "content_sha256": set(),
    }
    for case in cases:
        query = _query_key(case.get("query"))
        if query:
            result["query"].add(_digest(query))
        for chunk_id in case.get("expected_relevant_chunk_ids") or []:
            result["chunk_id"].add(str(chunk_id))
        if case.get("content_sha256"):
            result["content_sha256"].add(str(case["content_sha256"]).lower())
        for citation in case.get("expected_citations") or []:
            if not isinstance(citation, dict):
                continue
            document = str(citation.get("document_id") or "")
            chunk = str(citation.get("chunk_id") or "")
            locator = str(citation.get("source_locator") or "")
            if chunk:
                result["chunk_id"].add(chunk)
            if document and locator:
                result["source_locator"].add(_digest(f"{document}\0{locator}"))
    return result


def _duplicate_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    values: dict[str, list[str]] = {"case_id": [], **{key: [] for key in _keys([])}}
    for case in cases:
        if case.get("case_id"):
            values["case_id"].append(str(case["case_id"]))
        query = _query_key(case.get("query"))
        if query:
            values["query"].append(_digest(query))
        for chunk in case.get("expected_relevant_chunk_ids") or []:
            values["chunk_id"].append(str(chunk))
        if case.get("content_sha256"):
            values["content_sha256"].append(str(case["content_sha256"]).lower())
        for citation in case.get("expected_citations") or []:
            if isinstance(citation, dict):
                document = str(citation.get("document_id") or "")
                locator = str(citation.get("source_locator") or "")
                if document and locator:
                    values["source_locator"].append(_digest(f"{document}\0{locator}"))
    return {key: len(items) - len(set(items)) for key, items in values.items()}


def assess_independence(
    candidate: dict[str, Any], prior_datasets: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fail closed on missing history; never include customer strings in result."""
    candidate_cases = candidate.get("cases")
    if not isinstance(candidate_cases, list) or len(candidate_cases) != 50:
        raise ValueError("candidate must contain exactly 50 cases")
    if not prior_datasets:
        raise ValueError("at least one prior exposed dataset is required")
    prior_cases: list[dict[str, Any]] = []
    for dataset in prior_datasets:
        cases = dataset.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("each prior dataset must contain nonempty cases")
        prior_cases.extend(cases)
    if any(not isinstance(case, dict) for case in [*candidate_cases, *prior_cases]):
        raise ValueError("all cases must be objects")
    current = _keys(candidate_cases)
    prior = _keys(prior_cases)
    overlap = {key: len(values & prior[key]) for key, values in current.items()}
    duplicates = _duplicate_counts(candidate_cases)
    complete = all(
        case.get("case_id")
        and _query_key(case.get("query"))
        and case.get("expected_relevant_chunk_ids")
        and case.get("content_sha256")
        and case.get("expected_citations")
        for case in candidate_cases
    )
    return {
        "schema_version": "poc-03.independence-preflight.v1",
        "status": "PASS" if complete and not any(overlap.values()) and not any(duplicates.values()) else "FAIL",
        "candidate_case_count": len(candidate_cases),
        "prior_dataset_count": len(prior_datasets),
        "prior_case_count": len(prior_cases),
        "required_fields_complete": bool(complete),
        "overlap_counts": overlap,
        "candidate_duplicate_counts": duplicates,
        "meaning": "Mechanical exact-overlap preflight only; not semantic independence or quality acceptance.",
    }


def assess_files(candidate_path: Path, prior_paths: list[Path]) -> dict[str, Any]:
    candidate_bytes = candidate_path.read_bytes()
    prior_bytes = [path.read_bytes() for path in prior_paths]
    report = assess_independence(
        json.loads(candidate_bytes), [json.loads(value) for value in prior_bytes]
    )
    report["candidate_file_sha256"] = hashlib.sha256(candidate_bytes).hexdigest()
    report["prior_file_sha256"] = sorted(hashlib.sha256(value).hexdigest() for value in prior_bytes)
    return report
