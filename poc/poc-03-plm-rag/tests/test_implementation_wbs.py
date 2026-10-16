from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "poc/poc-03-plm-rag/scripts/build_implementation_wbs.py"
SOURCE = (
    ROOT
    / "artifacts/project-analysis/outputs/project-final-delivery-20260921-r6"
    / "internal-requirement-solution-delivery-package.json"
)

spec = importlib.util.spec_from_file_location("build_implementation_wbs", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class ImplementationWbsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.payload = module.build_wbs(source, "2026-09-21T00:00:00+08:00")

    def test_counts_and_boundaries(self) -> None:
        self.assertEqual("WBS_DRAFT_INTERNAL", self.payload["status"])
        self.assertEqual("NOT_FORMAL_WBS", self.payload["formal_status"])
        self.assertEqual(5, self.payload["summary"]["project_count"])
        self.assertEqual(60, self.payload["summary"]["task_count"])
        self.assertEqual(40, self.payload["summary"]["requirement_delivery_task_count"])
        self.assertEqual(20, self.payload["summary"]["project_control_task_count"])
        self.assertEqual(
            {"W0": 15, "W1": 10, "W2": 10, "W3": 15, "W4": 10},
            self.payload["summary"]["wave_counts"],
        )

    def test_task_ids_dependencies_and_traceability(self) -> None:
        tasks = self.payload["tasks"]
        task_ids = {task["task_id"] for task in tasks}
        self.assertEqual(len(tasks), len(task_ids))
        for task in tasks:
            self.assertTrue(set(task["predecessors"]).issubset(task_ids))
            self.assertEqual("DRAFT_NOT_SCHEDULED", task["status"])
        delivery_tasks = [task for task in tasks if task["task_type"] == "需求交付任务"]
        self.assertEqual(40, len(delivery_tasks))
        for task in delivery_tasks:
            self.assertTrue(task["requirement_id"])
            self.assertTrue(task["solution_id"])
            self.assertTrue(task["delivery_id"])
            self.assertTrue(task["trace_link"])

    def test_no_named_people_or_schedule_commitment(self) -> None:
        for task in self.payload["tasks"]:
            self.assertNotIn("owner_name", task)
            self.assertNotIn("start_date", task)
            self.assertNotIn("end_date", task)
            self.assertNotIn("duration_days", task)


if __name__ == "__main__":
    unittest.main()
