from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_caddy_windows_offline_input as target


class CaddyOfflineInputTests(unittest.TestCase):
    def test_checksum_entries_reject_duplicate(self) -> None:
        line = "a" * 128 + "  example.zip"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            target.checksum_entries(line + "\n" + line)

    def test_checksum_entries_reject_malformed(self) -> None:
        with self.assertRaisesRegex(ValueError, "malformed"):
            target.checksum_entries("not-a-checksum  example.zip")

    def test_missing_input_directory_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            target.audit(Path(__file__).parent / "definitely-not-present-caddy-input")


if __name__ == "__main__":
    unittest.main()
