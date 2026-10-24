"""Windows 11/PostgreSQL 18 proof for composed Handover Analysis HTTP."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/hnd-01-a04-a02-p02-review-owner/verify.py"
spec = importlib.util.spec_from_file_location("hnd_analysis_windows_fixture", SOURCE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


if __name__ == "__main__":
    os.environ["PLM_HND_SUBMISSION_VALIDATION"] = "1"
    os.environ["PLM_HND_ANALYSIS_COMPOSITION_VALIDATION"] = "1"
    module.main(use_http=True)
