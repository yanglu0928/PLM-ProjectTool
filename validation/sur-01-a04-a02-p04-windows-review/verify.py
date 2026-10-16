"""Windows 11/PostgreSQL 18 proof for Survey Review HTTP composition."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    fixture = runpy.run_path(str(
        ROOT / "validation/sur-01-a04-a02-p02-review-owner/verify.py"
    ))
    fixture["main"](use_http=True)
