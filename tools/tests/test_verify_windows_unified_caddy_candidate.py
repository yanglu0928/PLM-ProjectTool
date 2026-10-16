from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, EXPECTED_ADDITIONS, verify


class VerifyCaddyCandidateTests(unittest.TestCase):
    def test_fixed_identity_and_seven_additions(self) -> None:
        self.assertEqual(len(ARCHIVE_SHA256), 64)
        self.assertEqual(len(EXPECTED_ADDITIONS), 6)
        self.assertIn("payload/web/caddy.exe", EXPECTED_ADDITIONS)

    def test_missing_archive_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                verify(Path(directory) / "absent.zip")


if __name__ == "__main__":
    unittest.main()
