from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_current_app_packaged_https import _inputs  # noqa: E402


class CurrentAppHttpsBoundaryTests(unittest.TestCase):
    def test_wrong_candidate_digest_rejected_before_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.zip"
            candidate.write_bytes(b"test archive")
            stage = Path(tempfile.gettempdir()) / ("plm-current-app-stage-" + uuid.uuid4().hex[:12])
            stage.mkdir()
            try:
                with self.assertRaisesRegex(ValueError, "identity rejected"):
                    _inputs(candidate, stage, "0" * 64)
            finally:
                stage.rmdir()


if __name__ == "__main__":
    unittest.main()
