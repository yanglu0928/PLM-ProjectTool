"""Run the real PostgreSQL Capability state-owner scenario."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
os.environ["PLM_CAP_TERMINAL_VALIDATION"] = "1"
os.environ["PLM_CAP_STATE_VALIDATION"] = "1"
runpy.run_path(
    str(ROOT / "validation" / "cap-01-a04-a03-capability-subject" / "verify.py"),
    run_name="__main__",
)
