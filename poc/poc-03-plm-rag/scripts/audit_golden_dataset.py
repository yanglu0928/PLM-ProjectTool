from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.coverage import audit_golden_dataset_coverage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Golden Dataset diversity without persisting its content."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = audit_golden_dataset_coverage(dataset)
    report["generated_at"] = datetime.now().astimezone().isoformat()
    report["conclusion"] = (
        "Golden Dataset quality coverage passed."
        if report["status"] == "PASS"
        else "Golden Dataset quality coverage remains blocked."
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
