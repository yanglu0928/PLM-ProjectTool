from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = POC_DIR / "scripts" / "build_final_delivery_package.py"
SPEC = importlib.util.spec_from_file_location("final_delivery", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def sources(category: str = "标准功能", layer: str = "standard", resolution_id: str = ""):
    requirement = {
        "candidate_id": "REQC-P01-01",
        "project_id": "P01",
        "project_name": "测试项目",
        "category": category,
        "domain": "产品数据",
        "title": "物料管理",
        "statement": "配置物料管理。",
        "acceptance_draft": "样例通过。",
        "capability_match": "标准能力已有直接对照",
        "review_priority": "P0",
        "risk": "高" if resolution_id else "低",
        "resolution_id": resolution_id,
        "formal_status": "NOT_FORMAL_REQUIREMENT",
    }
    solution = {
        "solution_id": "SOLD-P01-01",
        "project_id": "P01",
        "project_name": "测试项目",
        "requirement_id": "REQC-P01-01",
        "requirement_title": "物料管理",
        "layer": layer,
        "build_mode": "标准配置" if layer == "standard" else "非标接口",
        "solution_name": "测试方案",
        "solution_outline": "方案摘要",
        "component": "component",
        "interface_spec": "接口设计",
        "migration_spec": "迁移设计",
        "permission_design": "权限设计",
        "acceptance_plan": "验收方案",
        "explicit_exclusion": "排除项",
        "dependency": "前提",
        "decision_trace": resolution_id,
        "evidence_link": "evidence-navigator.html#P01-01",
        "formal_status": "NOT_FORMAL_SOLUTION",
    }
    decision = {
        "decision_id": resolution_id,
        "project_id": "P01",
        "project_name": "测试项目",
        "issue": "待确认问题",
        "recommended_decision": "工作基线",
        "included_scope": "范围",
        "explicit_exclusion": "排除项",
        "acceptance_basis": "验收依据",
        "risk": "高",
        "evidence_link": "evidence-navigator.html#P01-01",
        "status": "ADOPTED_WORKING_BASELINE",
    }
    r4 = {
        "version": "R4",
        "fingerprint": "r4-fingerprint",
        "package_id": "R4",
        "projects": [{"project_id": "P01", "project_name": "测试项目"}],
        "decisions": [decision] if resolution_id else [],
        "requirements": [requirement],
    }
    r5 = {
        "version": "R5",
        "fingerprint": "r5-fingerprint",
        "source_fingerprint": "r4-fingerprint",
        "package_id": "R5",
        "solutions": [solution],
        "interface_specs": [solution["solution_id"]] if layer == "integration" else [],
        "migration_specs": [solution["solution_id"]] if layer == "data" else [],
        "permission_designs": [solution["solution_id"]] if layer == "security" else [],
    }
    return r4, r5


class FinalDeliveryPackageTests(unittest.TestCase):
    def test_rejects_unbound_solution_package(self) -> None:
        r4, r5 = sources()
        r5["source_fingerprint"] = "other"
        with self.assertRaisesRegex(ValueError, "not bound"):
            MODULE.build_package(r4, r5, "2026-09-21")

    def test_requires_exact_one_to_one_coverage(self) -> None:
        r4, r5 = sources()
        r5["solutions"][0]["requirement_id"] = "REQC-P01-02"
        with self.assertRaisesRegex(ValueError, "coverage"):
            MODULE.build_package(r4, r5, "2026-09-21")

    def test_standard_requirement_enters_wave_one(self) -> None:
        r4, r5 = sources()
        package = MODULE.build_package(r4, r5, "2026-09-21")
        item = package["delivery_items"][0]
        self.assertEqual("W1", item["delivery_wave"])
        self.assertEqual("INTERNAL_DELIVERY_DRAFT", item["delivery_status"])

    def test_working_baseline_enters_wave_zero_and_formalization_list(self) -> None:
        r4, r5 = sources("待确认项", "governance", "AID-ASM-P01-01")
        package = MODULE.build_package(r4, r5, "2026-09-21")
        self.assertEqual("W0", package["delivery_items"][0]["delivery_wave"])
        self.assertEqual(1, len(package["formalization_items"]))
        self.assertEqual("AWAITING_FORMAL_REVIEW", package["formalization_items"][0]["formalization_status"])

    def test_specialty_is_carried_into_delivery_package(self) -> None:
        r4, r5 = sources("非标功能", "integration")
        package = MODULE.build_package(r4, r5, "2026-09-21")
        self.assertEqual(["InterfaceSpec"], package["delivery_items"][0]["specialty_types"])
        self.assertEqual(1, len(package["specialty_items"]))

    def test_survey_outline_has_six_project_topics(self) -> None:
        r4, r5 = sources()
        package = MODULE.build_package(r4, r5, "2026-09-21")
        self.assertEqual(6, len(package["survey_outline"]))
        self.assertTrue(all(row["status"] == "RECOMMENDED_INTERNAL" for row in package["survey_outline"]))

    def test_output_never_promotes_formal_objects(self) -> None:
        r4, r5 = sources()
        package = MODULE.build_package(r4, r5, "2026-09-21")
        item = package["delivery_items"][0]
        self.assertEqual("NOT_FORMAL_REQUIREMENT", item["requirement_status"])
        self.assertEqual("NOT_FORMAL_SOLUTION", item["solution_status"])
        self.assertEqual("BLOCKED_BY_PHASE0_AND_REVIEW_GATES", package["projects"][0]["formal_readiness"])


if __name__ == "__main__":
    unittest.main()
