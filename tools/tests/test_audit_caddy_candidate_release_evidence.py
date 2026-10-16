from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_caddy_candidate_release_evidence import REQUIRED, classify  # noqa: E402


class CaddyReleaseEvidenceTests(unittest.TestCase):
    def fixture(self) -> tuple[set[str], dict]:
        names = set(REQUIRED)
        names.update(f"payload/third-party-licenses/ocr-python-notices/{i}.txt" for i in range(25))
        inventory = {"review_status": "REVIEW_REQUIRED", "base": {
            "review_status": "REVIEW_REQUIRED",
            "postgresql_pgvector": {"legal_review_status": "REVIEW_REQUIRED"},
            "unified": {"frontend_bundled_dependency_review": "REVIEW_REQUIRED"}},
            "caddy": {"downstream_notice_review_complete": False}}
        return names, inventory

    def test_open_evidence_not_misclassified_as_clearance(self) -> None:
        names, inventory = self.fixture()
        report = classify(names, inventory)
        self.assertFalse(report["release_eligible"])
        self.assertFalse(report["legal_clearance"])
        self.assertEqual(report["ocr_python_standalone_notice_files"], 25)

    def test_missing_notice_or_changed_review_state_rejected(self) -> None:
        names, inventory = self.fixture()
        names.remove("payload/third-party-licenses/ocr-python-notices/0.txt")
        with self.assertRaisesRegex(ValueError, "notice/source"):
            classify(names, inventory)
        names, inventory = self.fixture()
        inventory["caddy"]["downstream_notice_review_complete"] = True
        with self.assertRaisesRegex(ValueError, "review state"):
            classify(names, inventory)


if __name__ == "__main__":
    unittest.main()
