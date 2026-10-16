from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = POC_DIR / "scripts" / "build_desktop_discovery_requirements.py"
SPEC = importlib.util.spec_from_file_location("desktop_discovery_requirements", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DesktopDiscoveryRequirementsTests(unittest.TestCase):
    def test_actual_survey_is_strongest_evidence(self) -> None:
        items = [
            {"project_evidence": {"source_type": "SOLUTION"}},
            {"project_evidence": {"source_type": "ACTUAL_SURVEY"}},
        ]
        self.assertEqual("ACTUAL_SURVEY", MODULE.evidence_type(items))

    def test_pending_item_remains_blocked(self) -> None:
        item = {"category": "待确认项", "project_evidence": {"source_type": "ACTUAL_SURVEY"}}
        self.assertEqual("BLOCKED_BY_DECISION", MODULE.candidate_status(item))

    def test_standard_item_with_contract_can_be_draft_ready(self) -> None:
        item = {"category": "标准功能", "project_evidence": {"source_type": "CONTRACT"}}
        self.assertEqual("DRAFT_READY", MODULE.candidate_status(item))

    def test_solution_only_item_keeps_assumption(self) -> None:
        item = {"category": "差异项", "project_evidence": {"source_type": "SOLUTION"}}
        self.assertEqual("DRAFT_WITH_ASSUMPTION", MODULE.candidate_status(item))

    def test_execution_fingerprint_must_match_analysis(self) -> None:
        analysis = {"fingerprint": "analysis"}
        execution = {"source_analysis": {"fingerprint": "other"}}
        with self.assertRaisesRegex(ValueError, "does not reference"):
            MODULE.build_package(analysis, execution, "2026-09-21T00:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
