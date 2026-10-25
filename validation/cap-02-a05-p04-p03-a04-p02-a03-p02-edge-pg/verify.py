"""Run isolated Windows 11 Edge/Vue/FastAPI/PostgreSQL fixed Review proof."""

from __future__ import annotations

import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["PLM_CAP_GLOBAL_REVIEW_HTTP_VALIDATION"] = "1"
os.environ["PLM_CAP_FIXED_CONTENT_HTTP_VALIDATION"] = "1"
os.environ["PLM_CAP_FIXED_CONTENT_EDGE_VALIDATION"] = "1"
runpy.run_path(
    str(ROOT / "validation" / "cap-01-a05-a07-windows-composition" / "verify.py"),
    run_name="__main__",
)
