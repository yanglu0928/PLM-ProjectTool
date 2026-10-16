from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.corpus_partition import partition_parsed_documents  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Partition parsed local corpora by locked source type.")
    parser.add_argument("--local-validation-report", type=Path, required=True)
    parser.add_argument("--parsed-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--library-kind",
        choices=("STANDARD_LIBRARY", "CONTRACT_LIBRARY"),
        required=True,
    )
    parser.add_argument("--sanitized-report", type=Path, required=True)
    args = parser.parse_args()

    local_report = json.loads(args.local_validation_report.read_text(encoding="utf-8"))
    counts = partition_parsed_documents(
        local_report.get("results") or [],
        parsed_dir=args.parsed_dir,
        output_root=args.output_root,
        library_kind=args.library_kind,
    )
    source_count = sum(counts.values())
    status = "PASS" if source_count and source_count == local_report["summary"]["passed_count"] else "FAIL"
    report = {
        "schema_version": "poc-03.source-corpus-partition.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "library_kind": args.library_kind,
        "summary": {
            "source_document_count": source_count,
            "source_type_document_counts": counts,
        },
        "privacy": {
            "source_file_names_committed": False,
            "source_content_committed": False,
            "parsed_content_committed": False,
            "local_partition_root": "git-ignored artifacts/poc-03/source-corpora/partitioned/",
        },
    }
    args.sanitized_report.parent.mkdir(parents=True, exist_ok=True)
    args.sanitized_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
