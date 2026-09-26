from __future__ import annotations

import unittest
from dataclasses import replace

from plm_assistant.modules.workflow.domain.definition import (
    ChecklistItemDefinition, StageDefinition, WorkflowDefinition,
    WorkflowDefinitionError,
)


class WorkflowDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.item = ChecklistItemDefinition("HANDOVER_APPROVAL", True,
                                            review_policy_ref="REVIEW_POLICY_V1")
        self.first = StageDefinition("HANDOVER", 1, "GATE_HANDOVER_V1", (self.item,))
        self.second = StageDefinition(
            "SURVEY", 2, "GATE_SURVEY_V1",
            (ChecklistItemDefinition("SURVEY_RECORD", True,
                                     evidence_policy_ref="EVIDENCE_POLICY_V1"),),
        )

    def test_versioned_definition_has_ordered_unique_keys(self):
        definition = WorkflowDefinition(1, (self.first, self.second))
        self.assertEqual(tuple(stage.stage_key for stage in definition.stages),
                         ("HANDOVER", "SURVEY"))
        self.assertEqual(definition.version, 1)

    def test_stage_keys_and_order_must_be_unique_and_ordered(self):
        for stages in (
            (self.first, self.first),
            (self.first, replace(self.second, stage_key="HANDOVER")),
            (self.second, self.first),
            (self.first, replace(self.second, order=1)),
        ):
            with self.subTest(stages=stages), self.assertRaises(WorkflowDefinitionError):
                WorkflowDefinition(1, stages)

    def test_invalid_definition_and_stage_rejected(self):
        for version, stages in ((0, (self.first,)), (True, (self.first,)),
                                (1, ()), (1, [self.first])):
            with self.subTest(version=version), self.assertRaises(WorkflowDefinitionError):
                WorkflowDefinition(version, stages)
        for kwargs in (
            {"stage_key": "bad key"}, {"order": 0}, {"order": True},
            {"gate_policy_ref": ""}, {"checklist_items": ()},
            {"checklist_items": (self.item, self.item)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(WorkflowDefinitionError):
                replace(self.first, **kwargs)

    def test_invalid_checklist_rejected(self):
        for kwargs in (
            {"item_key": "bad key"}, {"item_key": ""},
            {"required": 1}, {"evidence_policy_ref": "bad policy"},
            {"review_policy_ref": "bad policy"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(WorkflowDefinitionError):
                replace(self.item, **kwargs)


if __name__ == "__main__":
    unittest.main()
