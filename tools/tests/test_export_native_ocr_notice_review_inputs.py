from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_native_ocr_notice_candidate import PREFIX  # noqa: E402
from export_native_ocr_notice_review_inputs import packet_members  # noqa: E402


class ExportNativeOcrReviewTests(unittest.TestCase):
    def test_exact_population_and_no_release_flag(self) -> None:
        evidence = [{"binary": f"binary-{n % 34}", "text_sha256": f"{n % 42:064x}",
                     "text_path": PREFIX + "texts/" + f"{n % 42:064x}" + ".txt",
                     "release_obligations_reviewed": "NO"} for n in range(61)]
        review = {"binary_count": 34, "evidence_record_count": 61,
                  "unique_text_count": 42, "release_eligible": False,
                  "legal_clearance": False, "review_status": "REVIEW_REQUIRED",
                  "evidence": evidence}
        self.assertEqual(len(packet_members(review)), 42)
        review["release_eligible"] = True
        with self.assertRaisesRegex(ValueError, "boundary differs"):
            packet_members(review)

    def test_absolute_or_misattributed_path_rejected(self) -> None:
        evidence = [{"binary": f"binary-{n % 34}", "text_sha256": f"{n % 42:064x}",
                     "text_path": PREFIX + "texts/" + f"{n % 42:064x}" + ".txt",
                     "release_obligations_reviewed": "NO"} for n in range(61)]
        review = {"binary_count": 34, "evidence_record_count": 61,
                  "unique_text_count": 42, "release_eligible": False,
                  "legal_clearance": False, "review_status": "REVIEW_REQUIRED",
                  "evidence": evidence}
        evidence[0]["text_path"] = "C:/local/secret.txt"
        with self.assertRaisesRegex(ValueError, "attribution differs"):
            packet_members(review)


if __name__ == "__main__":
    unittest.main()
