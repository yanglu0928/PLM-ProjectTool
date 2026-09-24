from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.holdout_import import (  # noqa: E402
    audit_holdout_dataset,
    build_holdout_dataset,
    build_sanitized_holdout_report,
    import_holdout_review,
)
from poc03_rag.review_import import ImportIssue  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _not_run_coverage() -> dict[str, Any]:
    return {
        "schema_version": "poc-03.holdout-coverage-result.v1",
        "status": "NOT_RUN",
        "summary": {"case_count": 0},
        "checks": {},
        "missing_source_types": [],
        "missing_classifications": [],
        "privacy": {
            "queries_committed": False,
            "answer_terms_committed": False,
            "reviewer_names_committed": False,
            "dataset_committed": False,
            "source_names_committed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strictly import the confirmed POC-03 independent holdout review"
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--review-package", type=Path, required=True)
    parser.add_argument("--holdout-lock", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=POC_DIR / "schema" / "holdout-dataset.schema.json",
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--coverage-report", type=Path, required=True)
    args = parser.parse_args()

    review_package = _load_json(args.review_package)
    holdout_lock = _load_json(args.holdout_lock)
    schema = _load_json(args.schema)
    result = import_holdout_review(args.workbook, review_package, holdout_lock)
    schema_valid = False
    output_written = False
    coverage = _not_run_coverage()
    if result.ready:
        try:
            dataset = build_holdout_dataset(
                result,
                holdout_lock,
                dataset_id=args.dataset_id,
                schema=schema,
            )
            schema_valid = True
            coverage = audit_holdout_dataset(dataset)
            if coverage["status"] == "PASS" and args.output is not None:
                _write_json(args.output, dataset)
                output_written = True
        except ValueError:
            result.issues.append(
                ImportIssue(
                    "SCHEMA_VALIDATION_FAILED",
                    "Independent holdout dataset failed the locked JSON Schema",
                )
            )

    _write_json(args.coverage_report, coverage)
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    report = build_sanitized_holdout_report(
        result,
        generated_at=generated_at,
        schema_valid=schema_valid,
        coverage_status=coverage["status"],
        output_written=output_written,
    )
    _write_json(args.report, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "approved_count": report["summary"]["approved_count"],
                "issue_count": report["summary"]["issue_count"],
                "schema_valid": schema_valid,
                "coverage_status": coverage["status"],
                "output_written": output_written,
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] in {"PASS", "READY", "AWAITING_HUMAN_CONFIRMATION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
