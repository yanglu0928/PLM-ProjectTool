"""Run the full Prototype chain and assert atomic business submission."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
verification = runpy.run_path(str(
    ROOT / "validation" / "prt-01-a07-a02-p02-review-owner" / "verify.py"
))


def main() -> None:
    verification["main"](verify_submission=True)
    print(
        "PRT_01_A07_A04_SUBMIT_REVIEW_PASS: current-fact drift rollback, "
        "atomic Review create/start/Prototype bind/receipt/Audit, persistent "
        "replay/conflict, ProjectManager and License gates verified on "
        "PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
