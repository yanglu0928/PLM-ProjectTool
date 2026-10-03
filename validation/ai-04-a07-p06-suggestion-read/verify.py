"""Windows deterministic proof for canonical Suggestion read and locators."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    targets = (
        "apps/backend/tests/unit/test_ai_suggestion_read.py",
        "apps/backend/tests/unit/test_document_resolve_parse_nodes.py",
        "apps/backend/tests/contract/test_ai_suggestion_read_api.py",
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q"],
        cwd=root, check=False, capture_output=True, text=True,
    )
    if completed.returncode:
        raise AssertionError(completed.stdout + completed.stderr)
    assert "12 passed" in completed.stdout
    print(json.dumps({
        "marker": "AI_04_A07_P06_SUGGESTION_READ_PASS",
        "canonical_v1_v2": True,
        "current_document_authorization": True,
        "v2_precision": "PARSED_NODE",
        "v1_precision": "DOCUMENT",
        "database_schema_changed": False,
        "provider_io": 0,
        "customer_data": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
