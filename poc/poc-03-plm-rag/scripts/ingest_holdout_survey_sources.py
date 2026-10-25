from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = POC_DIR.parents[1]
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(REPO_ROOT / "poc" / "poc-05-document-ocr" / "src"))

from poc03_rag.holdout_sources import ingest_holdout_sources  # noqa: E402
from poc05_parser import parse_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse and deduplicate new local survey sources for the POC-03 holdout")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=REPO_ROOT / "poc" / "poc-05-document-ocr" / "schema" / "parsed-document.schema.json",
    )
    args = parser.parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    _, report = ingest_holdout_sources(
        args.input_dir,
        args.output_root,
        historical_roots=args.historical_root,
        schema=schema,
        parse=parse_document,
    )
    report["generated_at"] = datetime.now().astimezone().isoformat()
    report["conclusion"] = (
        "New survey sources passed local parsing and duplicate checks."
        if report["status"] == "PASS"
        else "No eligible new survey source was ingested."
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
