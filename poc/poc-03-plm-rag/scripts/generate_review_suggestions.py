from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.review_import import load_candidate_records  # noqa: E402
from poc03_rag.review_suggestions import (  # noqa: E402
    build_review_suggestions,
    build_sanitized_suggestion_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate local-only POC-03 review suggestions without external AI services."
    )
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--sanitized-report", type=Path, required=True)
    args = parser.parse_args()

    candidates = load_candidate_records(args.candidates)
    suggestions = build_review_suggestions(candidates)
    report = build_sanitized_suggestion_report(
        suggestions,
        generated_at=datetime.now(UTC).isoformat(),
    )

    args.local_output.parent.mkdir(parents=True, exist_ok=True)
    args.local_output.write_text(
        json.dumps(suggestions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.sanitized_report.parent.mkdir(parents=True, exist_ok=True)
    args.sanitized_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS_FOR_HUMAN_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
