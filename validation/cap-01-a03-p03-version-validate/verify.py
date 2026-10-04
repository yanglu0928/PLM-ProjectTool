"""Run the complete Draft fixture including the P03 validation-report assertions."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    module = runpy.run_path(str(
        Path(__file__).resolve().parents[1]
        / "cap-01-a03-p02-version-create" / "verify.py"
    ))
    module["main"]()


if __name__ == "__main__":
    main()
