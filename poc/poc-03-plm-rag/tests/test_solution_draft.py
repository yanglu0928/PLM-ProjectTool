from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = POC_DIR / "scripts" / "build_solution_draft.py"
SPEC = importlib.util.spec_from_file_location("solution_draft", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SolutionDraftTests(unittest.TestCase):
    def test_standard_requirement_uses_configuration(self) -> None:
        requirement = {"category": "标准功能", "domain": "产品数据", "title": "BOM"}
        strategy = MODULE.solution_strategy(requirement, None)
        self.assertEqual("STANDARD_CONFIGURATION", strategy["archetype"])
        self.assertEqual("标准配置", strategy["build_mode"])

    def test_integration_requirement_uses_adapter(self) -> None:
        requirement = {"category": "非标功能", "domain": "ERP 集成", "title": "SAP 接口"}
        strategy = MODULE.solution_strategy(requirement, None)
        self.assertEqual("INTEGRATION_ADAPTER", strategy["archetype"])
        self.assertEqual("integration", strategy["layer"])

    def test_decision_profile_controls_solution(self) -> None:
        requirement = {"category": "待确认项", "domain": "接口", "title": "外部接口"}
        decision = {"profile": "UNKNOWN_EXTERNAL_INTEGRATION"}
        strategy = MODULE.solution_strategy(requirement, decision)
        self.assertEqual("READ_ONLY_INTEGRATION_SPIKE", strategy["archetype"])

    def test_invalid_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "fingerprinted R4"):
            MODULE.build_package({"version": "R3", "fingerprint": "x"}, "2026-09-21")

    def test_formal_requirement_is_rejected(self) -> None:
        source = {
            "version": "R4",
            "fingerprint": "x",
            "requirements": [{"formal_status": "FORMAL_REQUIREMENT"}],
        }
        with self.assertRaisesRegex(ValueError, "non-formal"):
            MODULE.build_package(source, "2026-09-21")

    def test_package_keeps_one_to_one_trace_and_nonformal_status(self) -> None:
        source = {
            "version": "R4",
            "fingerprint": "source",
            "package_id": "R4",
            "decisions": [],
            "projects": [{"project_id": "P01", "project_name": "项目"}],
            "requirements": [
                {
                    "candidate_id": "REQC-P01-01",
                    "project_id": "P01",
                    "project_name": "项目",
                    "category": "标准功能",
                    "domain": "产品数据",
                    "title": "物料管理",
                    "statement": "配置物料管理。",
                    "acceptance_draft": "样例通过。",
                    "review_priority": "P1",
                    "risk": "低",
                    "decision_basis": "标准能力",
                    "resolution_id": "",
                    "evidence_link": "evidence.html#x",
                    "formal_status": "NOT_FORMAL_REQUIREMENT",
                }
            ],
        }
        package = MODULE.build_package(source, "2026-09-21")
        self.assertEqual(1, len(package["solutions"]))
        solution = package["solutions"][0]
        self.assertEqual("REQC-P01-01", solution["requirement_trace"])
        self.assertEqual("NOT_FORMAL_SOLUTION", solution["formal_status"])
        self.assertEqual("SOLUTION_DRAFT_INTERNAL", solution["status"])


if __name__ == "__main__":
    unittest.main()
