from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_unified_ocr_license_sidecar import expected_entries  # noqa: E402
from plan_windows_unified_install import CANDIDATE_SHA256  # noqa: E402


def report() -> dict:
    rows = []
    for index in range(13):
        count = 13 if index == 0 else 1
        rows.append({
            "name": f"package-{index}", "version": "1.0",
            "review_status": "REVIEW_REQUIRED", "standalone_notice_sidecar_present": False,
            "embedded_notice_files": [
                {"path": f"payload/runtime/packages/package-{index}.dist-info/licenses/L{i}.txt",
                 "sha256": "a" * 64} for i in range(count)
            ],
        })
    return {"status": "EVIDENCE_GAPS_IDENTIFIED_NOT_LEGAL_CLEARANCE",
            "release_eligible": False, "candidate_sha256": CANDIDATE_SHA256,
            "new_python_distributions": rows}


class OcrNoticeSidecarTests(unittest.TestCase):
    def test_exact_notice_set(self) -> None:
        entries = expected_entries(report())
        self.assertEqual(len(entries), 25)
        self.assertTrue(all(item["path"].startswith("notices/") for item in entries))

    def test_unsafe_source_path_rejected(self) -> None:
        value = report()
        value["new_python_distributions"][0]["embedded_notice_files"][0]["path"] = (
            "payload/runtime/packages/../secret"
        )
        with self.assertRaises(ValueError):
            expected_entries(value)

    def test_duplicate_notice_target_rejected(self) -> None:
        value = report()
        notices = value["new_python_distributions"][0]["embedded_notice_files"]
        notices[1]["path"] = notices[0]["path"].replace("/L0.txt", "/l0.txt")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            expected_entries(value)

    def test_release_claim_rejected(self) -> None:
        value = report()
        value["release_eligible"] = True
        with self.assertRaisesRegex(ValueError, "identity rejected"):
            expected_entries(value)


if __name__ == "__main__":
    unittest.main()
