"""Run the real PostgreSQL Handover atomic submit-review scenario."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
os.environ["PLM_HND_SUBMISSION_VALIDATION"] = "1"
runpy.run_path(
    str(ROOT / "validation" / "hnd-01-a04-a02-p02-review-owner" / "verify.py"),
    run_name="__main__",
)
