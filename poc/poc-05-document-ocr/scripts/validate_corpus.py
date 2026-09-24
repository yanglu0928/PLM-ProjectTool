from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc05_parser import parse_document  # noqa: E402


FILES = [
    "sample.docx",
    "sample.pptx",
    "sample.xlsx",
    "sample.csv",
    "sample-text.pdf",
]


def normalize(value: str) -> str:
    return "".join(value.split()).replace("：", ":").lower()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def tool_version(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return output[0] if completed.returncode == 0 and output else None


def model_manifest() -> dict[str, Any]:
    configured = {
        "PP-OCRv5_mobile_det": os.environ.get("PADDLE_DET_MODEL_DIR"),
        "PP-OCRv5_mobile_rec": os.environ.get("PADDLE_REC_MODEL_DIR"),
    }
    models: list[dict[str, Any]] = []
    for model_name, configured_dir in configured.items():
        model_dir = (
            Path(configured_dir)
            if configured_dir
            else Path.home() / ".paddlex" / "official_models" / model_name
        )
        files = []
        if model_dir.is_dir():
            for path in sorted(item for item in model_dir.rglob("*") if item.is_file()):
                files.append(
                    {
                        "path": path.relative_to(model_dir).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": digest(path),
                    }
                )
        models.append(
            {
                "name": model_name,
                "source": "explicit_local_directory" if configured_dir else "paddlex_managed_cache",
                "file_count": len(files),
                "files": files,
            }
        )
    return {"models": models}


def term_recall(parsed: dict[str, Any], terms: list[str]) -> dict[str, Any]:
    text = normalize("\n".join(block["text"] for block in parsed["blocks"]))
    matches = {term: normalize(term) in text for term in terms}
    return {"matches": matches, "recall": sum(matches.values()) / len(matches)}


def run_ocrmypdf(input_pdf: Path, output_pdf: Path, log_path: Path) -> dict[str, Any]:
    output_pdf.unlink(missing_ok=True)
    compatibility = (
        POC_DIR.parent
        / "poc-01-python-313-dependencies"
        / "scripts"
        / "compat"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(compatibility), environment.get("PYTHONPATH", "")]
    )
    command = [
        sys.executable,
        "-m",
        "ocrmypdf",
        "--language",
        "chi_sim+eng",
        "--output-type",
        "pdfa-2",
        "--optimize",
        "0",
        "--oversample",
        "400",
        "--tesseract-pagesegmode",
        "6",
        "--deskew",
        str(input_pdf),
        str(output_pdf),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        env=environment,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )
    elapsed = time.perf_counter() - started
    log_path.write_text(completed.stderr.rstrip() + "\n", encoding="utf-8")
    parsed = parse_document(output_pdf).to_dict() if output_pdf.is_file() else None
    return {
        "status": "PASS" if completed.returncode == 0 and output_pdf.is_file() else "FAIL",
        "exit_code": completed.returncode,
        "duration_seconds": round(elapsed, 3),
        "pdfa_validated": "Output file is a PDF/A-2b (as expected)" in completed.stderr,
        "parsed": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=POC_DIR / "input")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    args.runtime_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads((POC_DIR / "fixture-spec.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (POC_DIR / "schema" / "parsed-document.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    results: dict[str, Any] = {}
    manifest: list[dict[str, Any]] = []
    overall_pass = True

    for file_name in FILES:
        path = args.input_dir / file_name
        manifest.append({"file": file_name, "size_bytes": path.stat().st_size, "sha256": digest(path)})
        started = time.perf_counter()
        parsed = parse_document(path).to_dict()
        elapsed = time.perf_counter() - started
        schema_errors = sorted(error.message for error in validator.iter_errors(parsed))
        locations = [block["source_locator"] for block in parsed["blocks"]]
        required_locations = spec["expected_sources"][file_name]
        source_checks = {
            prefix: any(prefix in location for location in locations) for prefix in required_locations
        }
        recall = term_recall(parsed, spec["shared_terms"])
        status = (
            "PASS"
            if not schema_errors and all(source_checks.values()) and recall["recall"] >= 0.6
            else "FAIL"
        )
        overall_pass = overall_pass and status == "PASS"
        output_path = args.runtime_dir / f"{path.name}.parsed.json"
        output_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        results[file_name] = {
            "status": status,
            "duration_seconds": round(elapsed, 3),
            "page_count": len(parsed["pages"]),
            "block_count": len(parsed["blocks"]),
            "table_row_count": sum(block["type"] == "table_row" for block in parsed["blocks"]),
            "schema_errors": schema_errors,
            "source_checks": source_checks,
            "term_recall": recall,
            "output": output_path.name,
        }

    scan_path = args.input_dir / "sample-scan.pdf"
    manifest.append(
        {"file": scan_path.name, "size_bytes": scan_path.stat().st_size, "sha256": digest(scan_path)}
    )
    for engine in ("paddle", "tesseract"):
        started = time.perf_counter()
        parsed = parse_document(scan_path, ocr_engine=engine).to_dict()
        elapsed = time.perf_counter() - started
        schema_errors = sorted(error.message for error in validator.iter_errors(parsed))
        recall = term_recall(parsed, spec["scan_terms"])
        status = "PASS" if not schema_errors and recall["recall"] >= 0.9 else "FAIL"
        overall_pass = overall_pass and status == "PASS"
        output_path = args.runtime_dir / f"sample-scan.{engine}.parsed.json"
        output_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        results[f"sample-scan.pdf::{engine}"] = {
            "status": status,
            "duration_seconds": round(elapsed, 3),
            "page_count": len(parsed["pages"]),
            "block_count": len(parsed["blocks"]),
            "schema_errors": schema_errors,
            "term_recall": recall,
            "metadata": parsed["metadata"],
            "output": output_path.name,
        }

    searchable_pdf = args.runtime_dir / "sample-scan.searchable.pdf"
    ocr_result = run_ocrmypdf(
        scan_path, searchable_pdf, args.runtime_dir / "ocrmypdf-stderr.txt"
    )
    parsed_searchable = ocr_result.pop("parsed")
    if parsed_searchable:
        schema_errors = sorted(error.message for error in validator.iter_errors(parsed_searchable))
        recall = term_recall(parsed_searchable, spec["scan_terms"])
        ocr_result["schema_errors"] = schema_errors
        ocr_result["term_recall"] = recall
        ocr_result["status"] = (
            "PASS"
            if ocr_result["status"] == "PASS"
            and ocr_result["pdfa_validated"]
            and not schema_errors
            and recall["recall"] >= 0.9
            else "FAIL"
        )
        (args.runtime_dir / "sample-scan.ocrmypdf.parsed.json").write_text(
            json.dumps(parsed_searchable, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    overall_pass = overall_pass and ocr_result["status"] == "PASS"
    results["sample-scan.pdf::ocrmypdf"] = ocr_result

    environment = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python_version": platform.python_version(),
        "packages": {
            name: package_version(name)
            for name in (
                "python-docx",
                "python-pptx",
                "openpyxl",
                "PyMuPDF",
                "pdfplumber",
                "Pillow",
                "paddleocr",
                "paddlepaddle",
                "pytesseract",
                "ocrmypdf",
                "jsonschema",
            )
        },
        "tools": {
            "tesseract": tool_version([os.environ.get("TESSERACT_EXE", "tesseract"), "--version"]),
            "ghostscript": tool_version(["gswin64c", "--version"]),
        },
    }
    (args.evidence_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.evidence_dir / "input-manifest.json").write_text(
        json.dumps({"corpus_version": spec["corpus_version"], "files": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.evidence_dir / "model-manifest.json").write_text(
        json.dumps(model_manifest(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "status": "PASS" if overall_pass else "FAIL",
        "platform": environment["platform"],
        "python_version": environment["python_version"],
        "results": results,
    }
    (args.evidence_dir / "validation-result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
