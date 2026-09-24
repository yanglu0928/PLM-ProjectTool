from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.r7_semantic_review import (  # noqa: E402
    build_r7_dataset,
    build_sanitized_r7_report,
    import_r7_semantic_review,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the POC-03 R7 semantic and citation review")
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=POC_DIR / "schema" / "golden-dataset.schema.json",
    )
    parser.add_argument("--dataset-id", default="poc-03-golden-2026-09-20-r7")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    golden = load_json(args.golden)
    package = load_json(args.package)
    schema = load_json(args.schema)
    result = import_r7_semantic_review(args.workbook, golden, package)
    output_written = False
    if result.ready:
        try:
            dataset = build_r7_dataset(
                golden,
                result,
                dataset_id=args.dataset_id,
                schema=schema,
            )
        except ValueError as error:
            report = build_sanitized_r7_report(
                result,
                generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                output_written=False,
            )
            report["status"] = "FAIL"
            report["issues"] = [
                {
                    "code": "SCHEMA_VALIDATION_FAILED",
                    "message": str(error),
                }
            ]
            report["conclusion"] = "R7 dataset export remains blocked."
            write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False))
            return 1
        write_json(args.output, dataset)
        output_written = True
    report = build_sanitized_r7_report(
        result,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        output_written=output_written,
    )
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if result.has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
