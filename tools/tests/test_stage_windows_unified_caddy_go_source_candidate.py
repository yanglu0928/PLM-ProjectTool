from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_caddy_go_source_candidate import KIND  # noqa: E402
from stage_windows_unified_caddy_go_source_candidate import NAME, stage  # noqa: E402
from verify_windows_unified_extract import ALLOWED_KINDS  # noqa: E402


class StageCaddyGoTests(unittest.TestCase):
    def test_new_kind_and_temp_root_name(self) -> None:
        self.assertIn(KIND, ALLOWED_KINDS)
        self.assertTrue(NAME.fullmatch("plm-caddy-go-stage-12345678"))
        self.assertFalse(NAME.fullmatch("plm-caddy-go-stage-.."))

    def test_existing_root_rejected_before_archive_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-caddy-go-stage-") as directory:
            with patch("stage_windows_unified_caddy_go_source_candidate.verify_candidate") as verify:
                with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                    stage(Path("candidate.zip"), Path("source.zip"), Path(directory))
                verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
