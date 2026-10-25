from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import date, datetime, timezone

from plm_assistant.modules.plan.application.plan_version_input import (
    DependencyInput, FixedVersionRef, RequirementVersionRef,
    parse_plan_version_draft,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionValidationSnapshot, evaluate_plan_version,
)


def _id() -> str:
    return str(uuid.uuid4())


def _ref() -> dict[str, object]:
    return {"resource_kind": "OUTLINE", "resource_id": _id(),
            "version_id": _id(), "spec_series_id": None, "spec_type": None}


def _item(item_id: str, solution_ref: dict[str, object], *, parent: str | None = None,
          level: int = 1) -> dict[str, object]:
    return {
        "wbs_item_id": item_id, "parent_item_id": parent,
        "wbs_code": f"WBS-{level}", "name": f"任务 {level}", "level": level,
        "category": "IMPLEMENTATION", "owner_ref": None,
        "support_role_refs": ["PROJECT_MANAGER"],
        "planned_start": "2026-10-01", "planned_finish": "2026-10-03",
        "duration_minutes": 120, "actual_start": None, "actual_finish": None,
        "item_state": "NOT_STARTED", "entry_conditions": ["来源已批准"],
        "acceptance_criteria": ["验证通过"], "requirement_refs": [],
        "solution_refs": [solution_ref], "prototype_refs": [],
        "evidence_refs": [], "output_refs": [], "risk": None,
        "explicit_exclusion": None,
    }


class PlanVersionValidationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id, self.plan_id, self.version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.requirement = RequirementVersionRef(uuid.uuid4(), uuid.uuid4())
        solution = _ref()
        root_id, child_id = _id(), _id()
        payload = {
            "approved_solution_refs": [solution],
            "wbs_items": [_item(root_id, solution),
                          _item(child_id, solution, parent=root_id, level=2)],
            "dependencies": [], "milestones": [], "calendar_ref": "CN_WORKDAY",
            "exclusions": [],
        }
        parsed = parse_plan_version_draft(payload, project_id=self.project_id,
                                          plan_id=self.plan_id)
        root = replace(parsed.input.wbs_items[0], requirement_refs=(self.requirement,))
        self.draft = replace(parsed.input, wbs_items=(root, parsed.input.wbs_items[1]))
        self.snapshot = PlanVersionValidationSnapshot(
            self.project_id, self.plan_id, self.version_id, 1, "DRAFT",
            b"f" * 32, self.draft)
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)

    def evaluate(self, snapshot=None, requirements=None):
        return evaluate_plan_version(
            self.snapshot if snapshot is None else snapshot,
            source_requirement_refs=(self.requirement,) if requirements is None else requirements,
            source_solution_refs=self.draft.approved_solution_refs,
            checked_at=self.now)

    def test_valid_snapshot_reports_mapped_coverage_without_state_change(self) -> None:
        report = self.evaluate()
        self.assertTrue(report.valid)
        self.assertEqual((), report.blocking_issues)
        self.assertEqual((), report.warnings)
        self.assertEqual((1, 1, 0, 0), (
            report.coverage_summary.requirement_total,
            report.coverage_summary.requirement_mapped,
            report.coverage_summary.requirement_excluded,
            report.coverage_summary.requirement_uncovered))
        self.assertEqual((1, 1, 0, 0), (
            report.coverage_summary.solution_total,
            report.coverage_summary.solution_mapped,
            report.coverage_summary.solution_excluded,
            report.coverage_summary.solution_uncovered))
        self.assertEqual("DRAFT", self.snapshot.version_state)
        self.assertEqual(self.now, report.checked_at)

    def test_reports_uncovered_sources_as_blocking_and_stable_codes(self) -> None:
        root, child = self.draft.wbs_items
        draft = replace(self.draft, wbs_items=(replace(root, requirement_refs=()), child))
        report = self.evaluate(replace(self.snapshot, draft=draft))
        self.assertFalse(report.valid)
        self.assertEqual(("REQUIREMENT_UNCOVERED",), report.blocking_issues)
        self.assertEqual(1, report.coverage_summary.requirement_uncovered)

    def test_detects_broken_hierarchy_date_and_dependency_cycle(self) -> None:
        root, child = self.draft.wbs_items
        malformed_root = replace(root, level=2,
                                 planned_start=date(2026, 10, 4),
                                 planned_finish=date(2026, 10, 3))
        dependencies = (
            DependencyInput(uuid.uuid4(), root.wbs_item_id, child.wbs_item_id,
                            "FS", 0, None, None),
            DependencyInput(uuid.uuid4(), child.wbs_item_id, root.wbs_item_id,
                            "FS", 0, None, None),
        )
        draft = replace(self.draft, wbs_items=(malformed_root, child),
                        dependencies=dependencies)
        report = self.evaluate(replace(self.snapshot, draft=draft))
        self.assertEqual(("DEPENDENCY_CYCLE", "WBS_DATE_RANGE_INVALID",
                          "WBS_HIERARCHY_INVALID"), report.blocking_issues)

    def test_stale_mapped_requirement_is_blocking_not_credited(self) -> None:
        replacement = RequirementVersionRef(uuid.uuid4(), uuid.uuid4())
        root, child = self.draft.wbs_items
        draft = replace(self.draft, wbs_items=(replace(root, requirement_refs=(replacement,)), child))
        report = self.evaluate(replace(self.snapshot, draft=draft))
        self.assertEqual(("REQUIREMENT_SOURCE_STALE", "REQUIREMENT_UNCOVERED"),
                         report.blocking_issues)
        self.assertEqual(0, report.coverage_summary.requirement_mapped)
        self.assertEqual(1, report.coverage_summary.requirement_uncovered)

    def test_current_solution_scope_is_authoritative_over_fixed_snapshot_refs(self) -> None:
        current = FixedVersionRef("OUTLINE", uuid.uuid4(), uuid.uuid4())
        report = evaluate_plan_version(
            self.snapshot, source_requirement_refs=(self.requirement,),
            source_solution_refs=(current,), checked_at=self.now)
        self.assertEqual(("SOLUTION_SOURCE_STALE", "SOLUTION_UNCOVERED"),
                         report.blocking_issues)
        self.assertEqual(1, report.coverage_summary.solution_uncovered)


if __name__ == "__main__":
    unittest.main()
