"""Prove packaged Review fixed-content and decision routes fail closed at signed License expiry."""

from __future__ import annotations

import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.pop("PLM_CAP_PACKAGED_REVIEW_NEGATIVE", None)
os.environ["PLM_CAP_PACKAGED_REVIEW_LICENSE_EXPIRY"] = "1"
runpy.run_path(
    str(ROOT / "validation" / "cap-02-a05-p04-p03-a04-p02-p05-p02-packaged-review" /
        "verify.py"),
    run_name="__main__",
)
