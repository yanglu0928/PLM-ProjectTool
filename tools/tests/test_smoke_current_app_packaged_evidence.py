from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_current_app_packaged_evidence import smoke  # noqa: E402


class PackagedEvidenceBoundaryTests(unittest.TestCase):
    def test_wrong_candidate_rejected_before_postgres(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            stage = parent / "plm-current-app-stage-synthetic1"
            stage.mkdir()
            candidate = parent / "candidate.zip"
            candidate.write_bytes(b"not the fixed candidate")
            with self.assertRaisesRegex(ValueError, "identity rejected"):
                smoke(candidate, stage, parent)


if __name__ == "__main__":
    unittest.main()
