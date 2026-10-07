"""Run the full Review chain and assert Approval Trace owner closure."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
verification = runpy.run_path(str(
    ROOT / "validation" / "prt-01-a07-a02-p02-review-owner" / "verify.py"
))


def main() -> None:
    verification["main"]()
    print(
        "PRT_01_A07_A03_P03_APPROVAL_TRACE_OWNER_PASS: approved terminal, "
        "idempotent replay, exact immutable manifest and six active business "
        "version edges for two approvals plus Trace failure rollback verified "
        "on PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
