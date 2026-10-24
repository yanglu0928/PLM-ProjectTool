from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_caddy_candidate import KIND
from stage_windows_unified_caddy_candidate import NAME, stage
from verify_windows_unified_extract import ALLOWED_KINDS


class StageCaddyTests(unittest.TestCase):
    def test_new_kind_and_temp_name(self) -> None:
        self.assertIn(KIND, ALLOWED_KINDS)
        self.assertTrue(NAME.fullmatch("plm-caddy-stage-12345678"))
        self.assertFalse(NAME.fullmatch("plm-caddy-stage-.."))

    def test_existing_or_outside_stage_rejected_before_archive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-caddy-test-") as directory:
            existing = Path(directory)
            with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                stage(existing / "missing.zip", existing)


if __name__ == "__main__":
    unittest.main()
