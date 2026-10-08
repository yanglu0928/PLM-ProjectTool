"""Run the real mixed Prototype/NOT_REQUIRED scope acceptance fixture."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
approved = runpy.run_path(str(
    ROOT / "validation/prt-01-a11-a05-p03-approved-prototype/verify.py"
))


if __name__ == "__main__":
    approved["main"](mixed_not_required=True)
    approved["main"](mixed_not_required=True, conflicting_decision=True)
