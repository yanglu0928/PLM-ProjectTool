from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.r5_label_review import (  # noqa: E402
    build_r5_dataset,
    build_sanitized_r5_report,
    import_r5_label_review,
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the POC-03 R5 lightweight label review")
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--r4-workbook", type=Path, required=True)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--dataset-id", default="poc-03-golden-2026-09-18-r5")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    golden = load_json(args.golden)
    quality = load_json(args.quality)
    result = import_r5_label_review(args.workbook, args.r4_workbook, golden, quality)
    output_written = False
    if result.ready:
        write_json(args.output, build_r5_dataset(golden, result, dataset_id=args.dataset_id))
        output_written = True
    report = build_sanitized_r5_report(
        result,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        output_written=output_written,
    )
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if result.has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
