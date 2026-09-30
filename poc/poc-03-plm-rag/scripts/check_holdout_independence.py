from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from poc03_rag.holdout_independence import assess_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-only new holdout exact-overlap preflight")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--prior", required=True, action="append", type=Path)
    args = parser.parse_args()
    report = assess_files(args.candidate, args.prior)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
