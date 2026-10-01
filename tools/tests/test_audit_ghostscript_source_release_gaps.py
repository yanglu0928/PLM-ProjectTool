from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ghostscript_source_release_gaps import REQUIRED, SOURCES, classify  # noqa: E402


class GhostscriptSourceReleaseGapTests(unittest.TestCase):
    def _fixture(self) -> tuple[set[str], dict, list[dict]]:
        names = set(REQUIRED)
        names.update(f"payload/third-party-licenses/notices/item-{i}" for i in range(152))
        names.update(f"payload/third-party-licenses/ocr-python-notices/item-{i}" for i in range(25))
        names.update(f"payload/third-party-licenses/frontend/item-{i}" for i in range(6))
        # Required contributes seven legal sidecars, for a total of 190.
        names.add("payload/third-party-licenses/caddy/windows_amd64.sbom")
        inventory = {"review_status": "REVIEW_REQUIRED", "base": {
            "unified": {"distribution_count": 106,
                        "frontend_bundled_dependency_review": "REVIEW_REQUIRED"},
            "postgresql_pgvector": {"legal_review_status": "REVIEW_REQUIRED"}},
            "caddy": {"sbom_component_count": 149,
                      "downstream_notice_review_complete": False},
            "ghostscript_source": {"review_status": "REVIEW_REQUIRED",
                                   "legal_clearance": False}}
        return names, inventory, [{"release_obligations_reviewed": "NO"} for _ in range(34)]

    def test_expected_evidence_remains_nonrelease(self) -> None:
        names, inventory, native = self._fixture()
        result = classify(names, inventory, native)
        self.assertFalse(result["release_eligible"])
        self.assertEqual(result["third_party_source_archives"], len(SOURCES))

    def test_product_notice_change_requires_new_review(self) -> None:
        names, inventory, native = self._fixture()
        names.add("NOTICE")
        with self.assertRaisesRegex(ValueError, "product legal files changed"):
            classify(names, inventory, native)

    def test_unreviewed_native_obligation_cannot_be_marked_complete(self) -> None:
        names, inventory, native = self._fixture()
        native[0]["release_obligations_reviewed"] = "YES"
        with self.assertRaisesRegex(ValueError, "review state differs"):
            classify(names, inventory, native)


if __name__ == "__main__":
    unittest.main()
