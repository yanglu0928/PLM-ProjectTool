from __future__ import annotations

import unittest
import uuid
from copy import deepcopy
from datetime import date

from plm_assistant.modules.plan.application.plan_version_input import (
    PlanVersionInputError,
    parse_plan_version_draft,
)


def _id() -> str:
    return str(uuid.uuid4())


def _ref(kind: str = "OUTLINE") -> dict[str, object]:
    result: dict[str, object] = {
        "resource_kind": kind, "resource_id": _id(), "version_id": _id(),
        "spec_series_id": None, "spec_type": None,
    }
    if kind == "STRUCTURED_SPEC":
        result["spec_series_id"] = _id()
        result["spec_type"] = "API_CONTRACT"
    return result


def _item(item_id: str, *, parent: str | None = None, level: int = 1) -> dict[str, object]:
    return {
        "wbs_item_id": item_id, "parent_item_id": parent,
        "wbs_code": f"WBS-{level}", "name": "实现任务", "level": level,
        "category": "IMPLEMENTATION", "owner_ref": None,
        "support_role_refs": ["PROJECT_MANAGER"],
        "planned_start": "2026-10-01", "planned_finish": "2026-10-03",
        "duration_minutes": 120, "actual_start": None, "actual_finish": None,
        "item_state": "NOT_STARTED", "entry_conditions": ["来源已批准"],
        "acceptance_criteria": ["验证通过"], "requirement_refs": [],
        "solution_refs": [], "prototype_refs": [], "evidence_refs": [],
        "output_refs": [], "risk": None, "explicit_exclusion": None,
    }


def _payload() -> dict[str, object]:
    root_id, child_id = _id(), _id()
    root = _item(root_id)
    child = _item(child_id, parent=root_id, level=2)
    child["wbs_code"] = "WBS-1.1"
    return {
        "approved_solution_refs": [_ref()],
        "wbs_items": [root, child], "dependencies": [], "milestones": [],
        "calendar_ref": "CN_WORKDAY", "exclusions": [],
    }


class PlanVersionInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id, self.plan_id = uuid.uuid4(), uuid.uuid4()
        self.payload = _payload()

    def parse(self, payload: object | None = None):
        return parse_plan_version_draft(
            self.payload if payload is None else payload,
            project_id=self.project_id, plan_id=self.plan_id)

    def test_strict_input_normalizes_and_fingerprints_path_scope(self) -> None:
        first = self.parse()
        second = self.parse(deepcopy(self.payload))
        self.assertEqual(first.request_fingerprint, second.request_fingerprint)
        self.assertEqual(first.input.wbs_items[0].planned_start, date(2026, 10, 1))
        self.assertEqual(len(first.request_fingerprint), 32)
        other_project = parse_plan_version_draft(
            self.payload, project_id=uuid.uuid4(), plan_id=self.plan_id)
        self.assertNotEqual(first.request_fingerprint, other_project.request_fingerprint)

    def test_rejects_unknown_fields_at_each_object_level(self) -> None:
        body = deepcopy(self.payload)
        body["database_column"] = "ignored"
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)
        body = deepcopy(self.payload)
        body["wbs_items"][0]["internal_fk"] = "ignored"
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)

    def test_rejects_invalid_parent_level_and_missing_dependency_target(self) -> None:
        body = deepcopy(self.payload)
        body["wbs_items"][1]["level"] = 3
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)
        body = deepcopy(self.payload)
        body["dependencies"] = [{
            "dependency_id": _id(), "predecessor_item_id": _id(),
            "successor_item_id": body["wbs_items"][0]["wbs_item_id"],
            "dependency_type": "FS", "lag": 0, "lag_unit": None, "lag_reason": None,
        }]
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)

    def test_rejects_cycles_self_edges_duplicate_ids_and_implicit_lag(self) -> None:
        body = deepcopy(self.payload)
        first, second = [item["wbs_item_id"] for item in body["wbs_items"]]
        body["dependencies"] = [
            {"dependency_id": _id(), "predecessor_item_id": first,
             "successor_item_id": second, "dependency_type": "FS",
             "lag": 0, "lag_unit": None, "lag_reason": None},
            {"dependency_id": _id(), "predecessor_item_id": second,
             "successor_item_id": first, "dependency_type": "FS",
             "lag": 0, "lag_unit": None, "lag_reason": None},
        ]
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)
        body = deepcopy(self.payload)
        first, second = [item["wbs_item_id"] for item in body["wbs_items"]]
        body["dependencies"] = [{
            "dependency_id": _id(), "predecessor_item_id": first,
            "successor_item_id": second, "dependency_type": "FS",
            "lag": 2, "lag_unit": None, "lag_reason": None,
        }]
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)

    def test_rejects_output_refs_and_preserves_typed_prototype_refs(self) -> None:
        body = deepcopy(self.payload)
        body["wbs_items"][0]["output_refs"] = [_id()]
        with self.assertRaises(PlanVersionInputError) as caught:
            self.parse(body)
        self.assertEqual(caught.exception.code, "OUTPUT_REFERENCE_UNAVAILABLE")
        body = deepcopy(self.payload)
        prototype = _ref("PROTOTYPE")
        body["wbs_items"][0]["prototype_refs"] = [prototype]
        parsed = self.parse(body)
        self.assertEqual(parsed.input.wbs_items[0].prototype_refs[0].resource_id,
                         uuid.UUID(prototype["resource_id"]))

    def test_rejects_invalid_date_ranges_and_duplicate_references(self) -> None:
        body = deepcopy(self.payload)
        body["wbs_items"][0]["planned_finish"] = "2026-09-30"
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)

    def test_rejects_wrong_prototype_kind_and_duplicate_milestones(self) -> None:
        body = deepcopy(self.payload)
        body["wbs_items"][0]["prototype_refs"] = [_ref("SECTION")]
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)
        body = deepcopy(self.payload)
        milestone = {
            "name": "上线", "target_date": "2026-11-01", "duration_days": 0,
            "acceptance_rule": "客户验收", "gate_ref": None, "wbs_item_refs": [],
        }
        body["milestones"] = [milestone, dict(milestone)]
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)
        body = deepcopy(self.payload)
        body["approved_solution_refs"].append(body["approved_solution_refs"][0])
        with self.assertRaises(PlanVersionInputError):
            self.parse(body)


if __name__ == "__main__":
    unittest.main()
