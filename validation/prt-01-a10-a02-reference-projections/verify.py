"""Aggregate Windows 11/PostgreSQL 18 proof for CR-PRT-002 read projections."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def execute(relative: str) -> None:
    module = runpy.run_path(str(ROOT / relative))
    module["main"]()


def main() -> None:
    execute("validation/req-01-a06-a03-version-read/verify.py")
    execute("validation/prt-01-a04-a05-template-read/verify.py")
    execute("validation/prt-01-a06-a04-version-read-validate/verify.py")
    print(
        "PRT_01_A10_A02_REFERENCE_PROJECTIONS_PASS: real Requirement acceptance "
        "identity, PROJECT Template and PrototypeVersion Document business locator, "
        "project isolation, authorization, zero read-side writes and Alembic drift "
        "verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
