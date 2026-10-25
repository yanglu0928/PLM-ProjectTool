from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.plan.application.create_plan_version import (
    PlanVersionCreateError, PlanVersionCreateService,
)
from plm_assistant.modules.plan.application.plan_version_input import (
    parse_plan_version_draft,
)
from plm_assistant.modules.plan.application.prove_approved_solution_input import (
    ApprovedSolutionInputProof,
)
from plm_assistant.modules.project.application.authorization import POLICIES


def _id() -> str:
    return str(uuid.uuid4())


def _draft(*, category: str = "IMPLEMENTATION", role: str = "PROJECT_MANAGER",
           calendar: str = "CN_WORKDAY"):
    outline_id, outline_version_id = _id(), _id()
    item_id = _id()
    return parse_plan_version_draft({
        "approved_solution_refs": [{
            "resource_kind": "OUTLINE", "resource_id": outline_id,
            "version_id": outline_version_id,
            "spec_series_id": None, "spec_type": None,
        }],
        "wbs_items": [{
            "wbs_item_id": item_id, "parent_item_id": None,
            "wbs_code": "1", "name": "Build", "level": 1,
            "category": category, "owner_ref": None,
            "support_role_refs": [role],
            "planned_start": None, "planned_finish": None,
            "duration_minutes": None, "actual_start": None, "actual_finish": None,
            "item_state": "NOT_STARTED", "entry_conditions": ["Ready"],
            "acceptance_criteria": ["Verified"], "requirement_refs": [],
            "solution_refs": [{
                "resource_kind": "OUTLINE", "resource_id": outline_id,
                "version_id": outline_version_id,
                "spec_series_id": None, "spec_type": None,
            }],
            "prototype_refs": [], "evidence_refs": [], "output_refs": [],
            "risk": None, "explicit_exclusion": None,
        }],
        "dependencies": [], "milestones": [],
        "calendar_ref": calendar, "exclusions": [],
    }, project_id=uuid.uuid4(), plan_id=uuid.uuid4())


class PlanVersionCreateOwnerPolicyTests(unittest.TestCase):
    def test_write_policy_is_limited_to_implementation_roles(self) -> None:
        policy = POLICIES["PLAN_VERSION_CREATE"]
        self.assertTrue(policy.write)
        self.assertEqual(policy.roles, frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }))

    def test_cr_plan_005_codes_accept_known_values(self) -> None:
        PlanVersionCreateService._validate_codes(_draft().input)

    def test_unknown_category_role_and_calendar_fail_closed(self) -> None:
        for kwargs in (
            {"category": "IMPLEMENTATION_2"},
            {"role": "BUSINESS_ANALYST"},
            {"calendar": "CUSTOM_CALENDAR"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(PlanVersionCreateError):
                    PlanVersionCreateService._validate_codes(_draft(**kwargs).input)

    def test_approved_solution_refs_must_be_persistable_on_wbs_rows(self) -> None:
        project_id = uuid.uuid4()
        source = _draft().input
        outline = source.approved_solution_refs[0]
        proof = ApprovedSolutionInputProof(
            project_id=project_id, outline_id=outline.resource_id,
            outline_version_id=outline.version_id,
            outline_content_fingerprint=b"o" * 32,
            requirement_refs=(), sections=(), requirement_scope_fingerprint=b"r" * 32,
        )
        PlanVersionCreateService._validate_solution_refs(project_id, source, proof)

        unrepresented = source.wbs_items[0]
        from dataclasses import replace
        invalid = replace(source, wbs_items=(replace(unrepresented, solution_refs=()),))
        with self.assertRaises(PlanVersionCreateError):
            PlanVersionCreateService._validate_solution_refs(project_id, invalid, proof)


if __name__ == "__main__":
    unittest.main()
