from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .source_roles import ACTUAL_SURVEY_RECORD_ROLE


SUPPORTED_SUFFIXES = {".docx", ".pptx", ".xlsx", ".csv", ".pdf"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parsed_content_sha256(parsed: dict[str, Any]) -> str:
    normalized = "\n".join(
        " ".join(str(block.get("text") or "").split())
        for block in parsed.get("blocks") or []
        if str(block.get("text") or "").strip()
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_historical_fingerprints(parsed_roots: list[Path]) -> tuple[set[str], set[str]]:
    source_hashes: set[str] = set()
    content_hashes: set[str] = set()
    for root in parsed_roots:
        for path in sorted(root.rglob("*.parsed.json")):
            parsed = json.loads(path.read_text(encoding="utf-8"))
            source_hash = str((parsed.get("source") or {}).get("sha256") or "").lower()
            if source_hash:
                source_hashes.add(source_hash)
            content_hashes.add(parsed_content_sha256(parsed))
    return source_hashes, content_hashes


def ingest_holdout_sources(
    input_dir: Path,
    output_root: Path,
    *,
    historical_roots: list[Path],
    schema: dict[str, Any],
    parse: Callable[[Path], Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validator = Draft202012Validator(schema)
    historical_source_hashes, historical_content_hashes = load_historical_fingerprints(historical_roots)
    seen_source_hashes: set[str] = set()
    seen_content_hashes: set[str] = set()
    results: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    survey_output = output_root / "SURVEY"
    survey_output.mkdir(parents=True, exist_ok=True)

    files = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    for path in files:
        source_hash = file_sha256(path).lower()
        if source_hash in historical_source_hashes:
            results.append({"status": "SKIPPED", "reason": "HISTORICAL_FILE_DUPLICATE"})
            continue
        if source_hash in seen_source_hashes:
            results.append({"status": "SKIPPED", "reason": "INPUT_FILE_DUPLICATE"})
            continue
        seen_source_hashes.add(source_hash)
        try:
            parsed_object = parse(path)
            parsed = parsed_object.to_dict() if hasattr(parsed_object, "to_dict") else parsed_object
        except Exception as error:  # noqa: BLE001 - per-file failure must be recorded and isolated
            results.append({"status": "FAIL", "reason": "PARSE_ERROR", "error_type": type(error).__name__})
            continue
        schema_errors = sorted(error.message for error in validator.iter_errors(parsed))
        if schema_errors:
            results.append({"status": "FAIL", "reason": "SCHEMA_ERROR", "schema_error_count": len(schema_errors)})
            continue
        parsed.setdefault("metadata", {})["evidence_role"] = ACTUAL_SURVEY_RECORD_ROLE
        parsed["metadata"]["evidence_authority"] = "PRIMARY_CUSTOMER_DISCOVERY_EVIDENCE"
        content_hash = parsed_content_sha256(parsed)
        if content_hash in historical_content_hashes:
            results.append({"status": "SKIPPED", "reason": "HISTORICAL_CONTENT_DUPLICATE"})
            continue
        if content_hash in seen_content_hashes:
            results.append({"status": "SKIPPED", "reason": "INPUT_CONTENT_DUPLICATE"})
            continue
        seen_content_hashes.add(content_hash)
        document_id = f"SURVEY-HO-{source_hash[:12].upper()}"
        output_path = survey_output / f"{document_id}.parsed.json"
        output_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        block_count = len(parsed.get("blocks") or [])
        character_count = sum(len(str(block.get("text") or "")) for block in parsed.get("blocks") or [])
        result = {
            "status": "PASS",
            "document_id": document_id,
            "block_count": block_count,
            "character_count": character_count,
            "output": output_path.name,
        }
        results.append(result)
        accepted.append(result)

    status_counts = Counter(result["status"] for result in results)
    reason_counts = Counter(result.get("reason", "") for result in results if result.get("reason"))
    report = {
        "schema_version": "poc-03.holdout-source-ingest-result.v1",
        "status": "PASS" if accepted else "FAIL",
        "summary": {
            "input_file_count": len(files),
            "accepted_document_count": len(accepted),
            "accepted_block_count": sum(result["block_count"] for result in accepted),
            "accepted_character_count": sum(result["character_count"] for result in accepted),
            "status_counts": dict(sorted(status_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
        },
        "checks": {
            "at_least_one_new_document": len(accepted) >= 1,
            "all_accepted_schema_valid": not any(result.get("reason") == "SCHEMA_ERROR" for result in results),
            "historical_file_hash_disjoint": not any(
                result.get("reason") == "HISTORICAL_FILE_DUPLICATE" for result in results
            ),
            "historical_content_hash_disjoint": not any(
                result.get("reason") == "HISTORICAL_CONTENT_DUPLICATE" for result in results
            ),
            "all_accepted_are_actual_survey_records": bool(accepted),
        },
        "source_governance": {
            "accepted_evidence_role": ACTUAL_SURVEY_RECORD_ROLE,
            "actual_survey_records": "PRIMARY_EVIDENCE",
            "survey_form_templates": "REFERENCE_ONLY_NOT_ELIGIBLE_FOR_HOLDOUT_QUOTA",
        },
        "privacy": {
            "source_names_committed": False,
            "source_hashes_committed": False,
            "document_content_committed": False,
            "parsed_documents_committed": False,
        },
        "results": results,
    }
    return accepted, report
