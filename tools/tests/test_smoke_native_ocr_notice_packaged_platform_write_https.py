from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_native_ocr_notice_packaged_platform_write_https import smoke  # noqa: E402


class NativeOcrNoticePackagedLoginTests(unittest.TestCase):
    def test_parent_mismatch_rejected_before_layout(self) -> None:
        paths = tuple(Path(name) for name in (
            "candidate", "parent", "ancestor", "grandparent", "matrix", "stage", "pristine", "target"))
        with patch("smoke_native_ocr_notice_packaged_platform_write_https.original_smoke") as original:
            def exercise(*args, **kwargs):
                kwargs["layout_verifier"](paths[0], Path("wrong"), paths[5], paths[6])
            original.side_effect = exercise
            with self.assertRaisesRegex(ValueError, "parent differs"):
                smoke(*paths)

    def test_incomplete_cleanup_cannot_report_pass(self) -> None:
        paths = tuple(Path(name) for name in (
            "candidate", "parent", "ancestor", "grandparent", "matrix", "stage", "pristine", "target"))
        with patch("smoke_native_ocr_notice_packaged_platform_write_https.original_smoke",
                   return_value={"synthetic_layout_file_count_before_injection": 21161,
                                 "fixed_candidate_unmodified": True,
                                 "synthetic_vault_targets_absent": False,
                                 "temporary_processes_stopped": True,
                                 "temporary_files_removed": True,
                                 "formal_trust_provisioned": False,
                                 "release_eligible": False}):
            with self.assertRaisesRegex(ValueError, "boundary differs"):
                smoke(*paths)


if __name__ == "__main__":
    unittest.main()
