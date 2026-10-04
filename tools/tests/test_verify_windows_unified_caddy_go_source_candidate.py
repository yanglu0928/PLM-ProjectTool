from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_windows_unified_caddy_go_source_candidate import verify  # noqa: E402


class CaddyGoSourceVerifyTests(unittest.TestCase):
    def test_missing_archive_rejected_before_parent_verification(self) -> None:
        with patch("verify_windows_unified_caddy_go_source_candidate.verify_source") as source:
            with self.assertRaisesRegex(ValueError, "archive size"):
                verify(Path("missing.zip"), Path("parent.zip"))
            source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
