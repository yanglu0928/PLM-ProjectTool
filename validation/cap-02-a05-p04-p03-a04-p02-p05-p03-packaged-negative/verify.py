"""Run extended Review denials on the identical fixed non-release candidate."""

from __future__ import annotations

import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["PLM_CAP_PACKAGED_REVIEW_NEGATIVE"] = "1"
runpy.run_path(
    str(ROOT / "validation" / "cap-02-a05-p04-p03-a04-p02-p05-p02-packaged-review" /
        "verify.py"),
    run_name="__main__",
)
