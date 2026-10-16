from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_current_app_packaged_runtime import audit  # noqa: E402


class PackagedRuntimeAuditBoundaryTests(unittest.TestCase):
    def test_wrong_candidate_identity_rejected_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            stage = parent / "plm-current-app-stage-synthetic1"
            stage.mkdir()
            candidate = parent / "candidate.zip"
            candidate.write_bytes(b"not the fixed candidate")
            with self.assertRaisesRegex(ValueError, "identity rejected"):
                audit(candidate, stage, parent)


if __name__ == "__main__":
    unittest.main()
