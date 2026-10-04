from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = POC_DIR / "scripts" / "build_survey_execution_package.py"
SPEC = importlib.util.spec_from_file_location("survey_execution_package", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SurveyExecutionPackageTests(unittest.TestCase):
    def test_wave_prefers_real_survey_and_contract(self) -> None:
        project = {"has_actual_survey": True, "has_contract_or_tech": True, "source_count": 3}
        self.assertEqual(1, MODULE.project_wave(project))

    def test_large_contract_evidence_can_enter_first_wave(self) -> None:
        project = {"has_actual_survey": False, "has_contract_or_tech": True, "source_count": 7}
        self.assertEqual(1, MODULE.project_wave(project))

    def test_scope_and_interface_topics_are_p0(self) -> None:
        self.assertEqual("P0", MODULE.task_priority("项目范围与组织", 2))
        self.assertEqual("P0", MODULE.task_priority("CAD/ERP 集成", 1))
        self.assertEqual("P1", MODULE.task_priority("样品与打样", 1))

    def test_required_materials_are_topic_specific(self) -> None:
        materials = MODULE.required_materials("SAP/OA 集成")
        self.assertIn("接口文档", materials)
        self.assertIn("系统版本", materials)

    def test_fingerprint_mismatch_blocks_generation(self) -> None:
        analysis = {"fingerprint": "a"}
        confirmation = {"analysis_fingerprint": "b", "decision": "APPROVED"}
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            MODULE.build_package(analysis, confirmation)


if __name__ == "__main__":
    unittest.main()
