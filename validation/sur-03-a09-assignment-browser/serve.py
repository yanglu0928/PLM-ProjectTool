"""Approved-Survey fixture wrapper for the Assignment/Response browser proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "validation/sur-02-a06-p02-round-browser/serve.py"
spec = importlib.util.spec_from_file_location("sur_assignment_browser_base", PATH)
assert spec is not None and spec.loader is not None
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

if __name__ == "__main__":
    with patch(
        "plm_assistant.entrypoints.production_login.create_windows_evidence_list_cursor_codec",
        return_value=EvidenceListCursorCodec(b"e" * 32),
    ):
        base.base.main()
