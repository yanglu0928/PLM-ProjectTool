from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.holdout_lock import (  # noqa: E402
    DEFAULT_QUOTAS,
    HoldoutQuotaError,
    build_holdout_lock,
    collect_contaminated_chunk_ids,
    load_json_lines,
    load_partitioned_chunks,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic contamination-resistant POC-03 holdout lock")
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--calibration-dataset", type=Path, required=True)
    parser.add_argument("--prompt-payload", type=Path, required=True)
    parser.add_argument("--review-package", type=Path, required=True)
    parser.add_argument("--retrieval-cache", type=Path, action="append", default=[])
    parser.add_argument("--project-id", default="POC03-SOURCE-CORPUS")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    calibration = load_json(args.calibration_dataset)
    prompt_payloads = load_json_lines(args.prompt_payload)
    review_package = load_json(args.review_package)
    retrieval_rows = [row for path in args.retrieval_cache for row in load_json_lines(path)]
    contaminated = collect_contaminated_chunk_ids(
        calibration,
        prompt_payloads,
        review_package,
        retrieval_rows,
    )
    chunks = load_partitioned_chunks(args.parsed_root, args.project_id)
    try:
        lock, report = build_holdout_lock(
            chunks,
            contaminated,
            project_id=args.project_id,
        )
    except HoldoutQuotaError as error:
        report = {
            "schema_version": "poc-03.holdout-lock-result.v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "status": "FAIL",
            "summary": {
                "target_count": sum(DEFAULT_QUOTAS.values()),
                "selected_count": 0,
                "eligible_counts": dict(sorted(error.eligible_counts.items())),
                "shortages": error.shortages,
                "contaminated_chunk_count": len(contaminated),
            },
            "checks": {
                "all_source_type_quotas_met": False,
                "lock_file_written": False,
            },
            "privacy": {
                "candidate_content_committed": False,
                "chunk_ids_committed": False,
                "source_names_committed": False,
                "source_locators_committed": False,
                "lock_file_committed": False,
            },
            "known_limit": (
                "At least one new survey source is required. Reusing exposed survey chunks would "
                "invalidate the independent holdout."
            ),
            "conclusion": "Independent holdout source lock failed closed because a source quota is unavailable.",
        }
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    report["generated_at"] = datetime.now().astimezone().isoformat()
    report["conclusion"] = (
        "Independent holdout sources are locked and ready for human-authored queries and labels."
        if report["status"] == "PASS"
        else "Independent holdout source lock failed."
    )
    write_json(args.output, lock)
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
