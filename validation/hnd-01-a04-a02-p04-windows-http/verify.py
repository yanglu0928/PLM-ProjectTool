"""Windows 11/PostgreSQL 18 proof for composed Handover Review HTTP writes."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/hnd-01-a04-a02-p02-review-owner/verify.py"
spec = importlib.util.spec_from_file_location("hnd_review_http_fixture", SOURCE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


if __name__ == "__main__":
    module.main(use_http=True)
