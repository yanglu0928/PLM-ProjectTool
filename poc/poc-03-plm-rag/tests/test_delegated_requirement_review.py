from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = POC_DIR / "scripts" / "build_delegated_requirement_review.py"
SPEC = importlib.util.spec_from_file_location("delegated_requirement_review", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DelegatedRequirementReviewTests(unittest.TestCase):
    def test_project_product_quote_profile(self) -> None:
        result = MODULE.resolve_assumption({"issue": "一项目多产品的项目、产品、报价单关系"})
        self.assertEqual("PROJECT_PRODUCT_QUOTATION_MODEL", result["profile"])
        self.assertIn("独立维护多版本", result["decision"])

    def test_fallback_is_conservative(self) -> None:
        result = MODULE.resolve_assumption({"issue": "没有已知规则的事项"})
        self.assertEqual("CONSERVATIVE_SCOPE_DEFAULT", result["profile"])
        self.assertIn("未知部分不承诺", result["decision"])

    def test_invalid_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "fingerprinted R3"):
            MODULE.build_package({"version": "R2", "fingerprint": "x"}, "2026-09-21")

    def test_duplicate_candidate_ids_are_rejected(self) -> None:
        source = {
            "version": "R3",
            "fingerprint": "x",
            "requirements": [{"candidate_id": "A"}, {"candidate_id": "A"}],
        }
        with self.assertRaisesRegex(ValueError, "unique"):
            MODULE.build_package(source, "2026-09-21")

    def test_delegated_decision_does_not_create_formal_requirement(self) -> None:
        source = {
            "version": "R3",
            "fingerprint": "source-fingerprint",
            "package_id": "R3",
            "projects": [
                {"project_id": "P01", "project_name": "项目", "status": "READY"}
            ],
            "assumptions": [
                {
                    "assumption_id": "ASM-P01-01",
                    "project_id": "P01",
                    "project_name": "项目",
                    "issue": "报价模板和计算对账样本是否齐备",
                    "basis": "缺少样例",
                    "evidence_link": "evidence.html#x",
                }
            ],
            "requirements": [
                {
                    "candidate_id": "REQC-P01-01",
                    "project_id": "P01",
                    "project_name": "项目",
                    "category": "待确认项",
                    "title": "报价模板和计算对账样本是否齐备",
                    "status": "BLOCKED_BY_DECISION",
                }
            ],
        }
        package = MODULE.build_package(source, "2026-09-21")
        requirement = package["requirements"][0]
        self.assertEqual("INTERNAL_REVIEW_DRAFT", requirement["review_status"])
        self.assertEqual("NOT_FORMAL_REQUIREMENT", requirement["formal_status"])
        self.assertEqual("P0", requirement["review_priority"])
        self.assertTrue(requirement["resolution_id"])


if __name__ == "__main__":
    unittest.main()
