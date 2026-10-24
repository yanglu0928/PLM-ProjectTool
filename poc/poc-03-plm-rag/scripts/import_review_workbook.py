from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.review_import import (  # noqa: E402
    build_golden_dataset,
    build_sanitized_import_report,
    import_review_workbook,
    load_candidate_records,
)


def _required_export_arguments(args: argparse.Namespace) -> None:
    required = {
        "--output": args.output,
        "--dataset-id": args.dataset_id,
        "--embedding-provider": args.embedding_provider,
        "--embedding-model": args.embedding_model,
        "--embedding-dimension": args.embedding_dimension,
        "--index-version": args.index_version,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        raise ValueError(f"Export requires: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a local POC-03 review workbook and export approved cases."
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=POC_DIR / "schema" / "golden-dataset.schema.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dataset-id")
    parser.add_argument("--embedding-provider")
    parser.add_argument("--embedding-model")
    parser.add_argument("--embedding-dimension", type=int)
    parser.add_argument("--index-version")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    candidates = load_candidate_records(args.candidates)
    result = import_review_workbook(
        args.workbook,
        candidates,
        timezone_name=args.timezone,
    )
    output_written = False
    if not args.validate_only and not result.has_errors and 100 <= len(result.cases) <= 200:
        _required_export_arguments(args)
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        dataset = build_golden_dataset(
            result,
            dataset_id=args.dataset_id,
            provider=args.embedding_provider,
            model=args.embedding_model,
            dimension=args.embedding_dimension,
            index_version=args.index_version,
            schema=schema,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_written = True

    report = build_sanitized_import_report(
        result,
        generated_at=datetime.now(UTC).isoformat(),
        output_written=output_written,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if result.has_errors:
        return 1
    if args.validate_only:
        return 0
    return 0 if output_written else 2


if __name__ == "__main__":
    raise SystemExit(main())
