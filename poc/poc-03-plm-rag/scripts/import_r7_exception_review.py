from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.r7_exception_review import (  # noqa: E402
    build_sanitized_r71_report,
    import_r7_exception_review,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Strictly import the single-case R7.1 exception review")
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--r7-dataset", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=POC_DIR / "schema" / "golden-dataset.schema.json")
    parser.add_argument("--dataset-id", default="poc-03-golden-2026-09-20-r7-1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    result = import_r7_exception_review(
        args.workbook,
        load_json(args.r7_dataset),
        load_json(args.package),
        dataset_id=args.dataset_id,
        schema=load_json(args.schema),
    )
    output_written = False
    if result.ready and result.dataset is not None:
        write_json(args.output, result.dataset)
        output_written = True
    report = build_sanitized_r71_report(
        result,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        output_written=output_written,
    )
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
