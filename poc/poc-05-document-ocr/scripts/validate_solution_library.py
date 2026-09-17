from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc05_parser import parse_document  # noqa: E402


SUPPORTED_SUFFIXES = {".docx", ".pptx", ".xlsx", ".csv", ".pdf"}
OOXML_SUFFIXES = {".docx", ".pptx", ".xlsx"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def ooxml_package_check(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() not in OOXML_SUFFIXES:
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        return {"status": "FAIL", "error_type": type(exc).__name__}
    return {"status": "PASS" if bad_member is None else "FAIL"}


def pdf_profile(path: Path, low_text_threshold: int) -> dict[str, Any]:
    with pymupdf.open(path) as document:
        counts = [len("".join(page.get_text().split())) for page in document]
    low_text_pages = [index + 1 for index, count in enumerate(counts) if count < low_text_threshold]
    low_text_page_ratio = len(low_text_pages) / len(counts) if counts else 0.0
    if not low_text_pages:
        classification = "text"
    elif len(low_text_pages) == len(counts):
        classification = "scan"
    elif low_text_page_ratio <= 0.1:
        classification = "text_with_sparse_low_text_pages"
    else:
        classification = "mixed"
    return {
        "classification": classification,
        "page_count": len(counts),
        "text_character_count": sum(counts),
        "low_text_page_count": len(low_text_pages),
        "low_text_page_ratio": round(low_text_page_ratio, 4),
        "low_text_threshold": low_text_threshold,
    }


def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "document_id",
        "extension",
        "size_bytes",
        "status",
        "parser_mode",
        "duration_seconds",
        "page_count",
        "block_count",
        "table_row_count",
        "ocr_line_count",
        "warning_count",
        "schema_error_count",
        "source_unchanged",
        "package_check",
        "pdf_profile",
        "error_type",
    )
    return {key: result[key] for key in allowed if key in result}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only POC-05 validation for a local solution-document library."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--sanitized-report", type=Path, required=True)
    parser.add_argument("--ocr-engine", choices=("paddle", "tesseract"), default="paddle")
    parser.add_argument("--pdf-low-text-threshold", type=int, default=20)
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(input_dir)
    runtime_dir = args.runtime_dir.resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    args.sanitized_report.parent.mkdir(parents=True, exist_ok=True)

    schema = json.loads(
        (POC_DIR / "schema" / "parsed-document.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    files = sorted(
        (path for path in input_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(input_dir).as_posix().casefold(),
    )

    local_results: list[dict[str, Any]] = []
    public_results: list[dict[str, Any]] = []
    started_all = time.perf_counter()

    for index, path in enumerate(files, start=1):
        document_id = f"SL-{index:03d}"
        relative_path = path.relative_to(input_dir).as_posix()
        suffix = path.suffix.lower()
        print(f"{document_id} START extension={suffix or '<none>'}", flush=True)
        stat_before = path.stat()
        hash_before = digest(path)
        result: dict[str, Any] = {
            "document_id": document_id,
            "relative_path": relative_path,
            "extension": suffix or "<none>",
            "size_bytes": stat_before.st_size,
            "sha256": hash_before,
            "package_check": ooxml_package_check(path),
        }

        if suffix not in SUPPORTED_SUFFIXES:
            result.update(
                {
                    "status": "UNSUPPORTED",
                    "parser_mode": "none",
                    "source_unchanged": True,
                }
            )
            local_results.append(result)
            public_results.append(sanitize_result(result))
            print(f"{document_id} END status=UNSUPPORTED", flush=True)
            continue

        parser_mode = "structural"
        pdf_details = None
        ocr_engine = None
        started = time.perf_counter()
        try:
            if suffix == ".pdf":
                pdf_details = pdf_profile(path, args.pdf_low_text_threshold)
                if pdf_details["classification"] in {"scan", "mixed"}:
                    ocr_engine = args.ocr_engine
                    parser_mode = f"ocr:{ocr_engine}"
                else:
                    parser_mode = "pdf_text"
            parsed = parse_document(path, ocr_engine=ocr_engine).to_dict()
            schema_errors = sorted(error.message for error in validator.iter_errors(parsed))
            parsed_output = runtime_dir / f"{document_id}.parsed.json"
            parsed_output.write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            block_types = Counter(block["type"] for block in parsed["blocks"])
            status = "PASS"
            if schema_errors:
                status = "FAIL_SCHEMA"
            elif not parsed["blocks"]:
                status = "FAIL_EMPTY"
            result.update(
                {
                    "status": status,
                    "parser_mode": parser_mode,
                    "duration_seconds": round(time.perf_counter() - started, 3),
                    "page_count": len(parsed["pages"]),
                    "block_count": len(parsed["blocks"]),
                    "table_row_count": block_types["table_row"],
                    "ocr_line_count": block_types["ocr_line"],
                    "warning_count": len(parsed["warnings"]),
                    "schema_error_count": len(schema_errors),
                    "schema_errors": schema_errors,
                    "pdf_profile": pdf_details,
                    "parsed_output": parsed_output.name,
                }
            )
        except Exception as exc:  # evidence records exact details only in ignored local output
            result.update(
                {
                    "status": "FAIL_PARSE",
                    "parser_mode": parser_mode,
                    "duration_seconds": round(time.perf_counter() - started, 3),
                    "pdf_profile": pdf_details,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

        stat_after = path.stat()
        hash_after = digest(path)
        result["source_unchanged"] = (
            stat_before.st_size == stat_after.st_size
            and stat_before.st_mtime_ns == stat_after.st_mtime_ns
            and hash_before == hash_after
        )
        result["sha256_after"] = hash_after
        local_results.append(result)
        public_results.append(sanitize_result(result))
        print(f"{document_id} END status={result['status']}", flush=True)

    status_counts = Counter(result["status"] for result in local_results)
    supported_count = sum(result["extension"] in SUPPORTED_SUFFIXES for result in local_results)
    passed_count = status_counts["PASS"]
    failed_count = supported_count - passed_count
    unsupported_count = status_counts["UNSUPPORTED"]
    unchanged_count = sum(bool(result.get("source_unchanged")) for result in local_results)
    overall_status = "PASS"
    if failed_count:
        overall_status = "FAIL"
    elif unsupported_count:
        overall_status = "PARTIAL_PASS"

    generated_at = datetime.now(UTC).isoformat()
    local_report = {
        "status": overall_status,
        "generated_at": generated_at,
        "input_dir": str(input_dir),
        "quality_scope": "schema_and_structure_only_no_content_accuracy_ground_truth",
        "summary": {
            "file_count": len(files),
            "supported_count": supported_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "unsupported_count": unsupported_count,
            "source_unchanged_count": unchanged_count,
            "duration_seconds": round(time.perf_counter() - started_all, 3),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "results": local_results,
    }
    (runtime_dir / "local-validation-result.json").write_text(
        json.dumps(local_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    public_report = {
        "status": overall_status,
        "generated_at": generated_at,
        "corpus": "local_solution_library_redacted",
        "privacy": {
            "source_files_committed": False,
            "source_names_committed": False,
            "parsed_content_committed": False,
            "local_mapping_location": "git-ignored artifacts/poc-05/solution-library/",
        },
        "quality_scope": "schema_and_structure_only_no_content_accuracy_ground_truth",
        "summary": local_report["summary"],
        "extension_counts": dict(
            sorted(Counter(result["extension"] for result in local_results).items())
        ),
        "results": public_results,
    }
    args.sanitized_report.write_text(
        json.dumps(public_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(public_report, ensure_ascii=False, indent=2))
    return 0 if overall_status in {"PASS", "PARTIAL_PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
