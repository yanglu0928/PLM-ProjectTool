from dataclasses import FrozenInstanceError
import unittest

from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.definition import WorkflowDefinitionError


class WorkflowCatalogTests(unittest.TestCase):
    def test_exact_historical_stage_order(self):
        definition = six_stage_definition(1)
        self.assertEqual(definition.version, 1)
        self.assertEqual(tuple((s.stage_key, s.order) for s in definition.stages), (
            ("HANDOVER", 1), ("SURVEY", 2), ("REQUIREMENT", 3),
            ("PROTOTYPE", 4), ("SOLUTION", 5), ("PLAN", 6),
        ))

    def test_required_items_and_explicit_policy_references(self):
        definition = six_stage_definition()
        keys = []
        for stage in definition.stages:
            self.assertEqual(stage.gate_policy_ref, f"GATE_{stage.stage_key}_V1")
            self.assertEqual(len(stage.checklist_items), 2)
            for item in stage.checklist_items:
                keys.append(item.item_key)
                self.assertIs(item.required, True)
                self.assertEqual(item.evidence_policy_ref, "EVIDENCE_FIXED_PROJECT_V1")
                self.assertEqual(item.review_policy_ref, f"REVIEW_{stage.stage_key}_V1")
        self.assertEqual(len(set(keys)), 12)
        self.assertEqual(tuple(keys), (
            "HANDOVER_BASELINE", "HANDOVER_ISSUES", "SURVEY_ACTUAL_SOURCES",
            "SURVEY_CONCLUSION", "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE",
            "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE", "SOLUTION_APPROVED_SET",
            "SOLUTION_COVERAGE", "PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION",
        ))

    def test_configuration_has_no_mutable_project_state(self):
        definition = six_stage_definition()
        for obj, field, value in (
            (definition, "version", 2), (definition.stages[0], "order", 2),
            (definition.stages[0].checklist_items[0], "required", False),
        ):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(obj, field, value)
        self.assertIs(six_stage_definition(), definition)
        self.assertFalse(hasattr(definition, "current_stage_key"))

    def test_unknown_or_ambiguous_versions_fail_closed(self):
        for version in (0, 2, -1, True, False, "1", 1.0, None):
            with self.subTest(version=version), self.assertRaises(WorkflowDefinitionError):
                six_stage_definition(version)


if __name__ == "__main__":
    unittest.main()
