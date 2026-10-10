from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_native_ocr_notice_candidate import INDEX, PREFIX, README  # noqa: E402
from rehearse_windows_unified_native_ocr_notice_layout import license_targets, rehearse  # noqa: E402


class NativeOcrNoticeLayoutTests(unittest.TestCase):
    def test_existing_output_rejected_before_archive_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as output:
            with patch("rehearse_windows_unified_native_ocr_notice_layout.verify_candidate") as verify:
                with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                    rehearse(Path("candidate.zip"), Path("parent.zip"), Path("ancestor.zip"),
                             Path("grandparent.zip"), Path("matrix.csv"), Path("stage"), Path(output))
                verify.assert_not_called()

    def test_license_mapping_requires_exact_attribution(self) -> None:
        evidence = [{"text_path": PREFIX + "texts/" + f"{n:064x}" + ".txt",
                     "text_sha256": f"{n:064x}", "release_obligations_reviewed": "NO"}
                    for n in range(42)]
        evidence += evidence[:19]
        mapping = {item["text_path"]: "app/third-party-licenses/native-ocr/texts/"
                   + item["text_sha256"] + ".txt" for item in evidence}
        mapping[INDEX] = "app/third-party-licenses/native-ocr/review-map.json"
        mapping[README] = "app/third-party-licenses/native-ocr/README.txt"
        review = {"evidence": evidence, "unique_text_count": 42,
                  "legal_clearance": False, "release_eligible": False}
        self.assertEqual(len(license_targets(mapping, review)), 42)
        mapping[INDEX] = "wrong/review-map.json"
        with self.assertRaisesRegex(ValueError, "sidecar mapping differs"):
            license_targets(mapping, review)


if __name__ == "__main__":
    unittest.main()
