from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_native_ocr_notice_candidate import KIND  # noqa: E402
from stage_windows_unified_native_ocr_notice_candidate import NAME, stage  # noqa: E402
from verify_windows_unified_extract import ALLOWED_KINDS  # noqa: E402


class StageNativeOcrNoticeTests(unittest.TestCase):
    def test_kind_and_direct_temp_name(self) -> None:
        self.assertIn(KIND, ALLOWED_KINDS)
        self.assertTrue(NAME.fullmatch("plm-native-ocr-stage-12345678"))
        self.assertFalse(NAME.fullmatch("plm-native-ocr-stage-.."))

    def test_existing_root_rejected_before_archive_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-native-ocr-stage-") as directory:
            with patch("stage_windows_unified_native_ocr_notice_candidate.verify_candidate") as verify:
                with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                    stage(Path("candidate.zip"), Path("parent.zip"), Path("ancestor.zip"),
                          Path("grandparent.zip"), Path("matrix.csv"), Path(directory))
                verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
