from dataclasses import replace
import unittest

from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.transition import (
    ChecklistState, StageState, WorkflowState, WorkflowTransitionError,
    validate_forward_structure,
)


class WorkflowTransitionTests(unittest.TestCase):
    def setUp(self):
        self.definition = six_stage_definition()
        self.arguments = dict(
            workflow_state=WorkflowState.ACTIVE, current_stage_key="HANDOVER",
            target_stage_key="SURVEY", expected_version=0, lock_version=0,
            project_archived=False,
        )

    def test_exact_frozen_state_values(self):
        self.assertEqual(tuple(WorkflowState), ("NOT_STARTED", "ACTIVE", "COMPLETED"))
        self.assertEqual(tuple(StageState), ("NOT_STARTED", "ACTIVE", "BLOCKED", "COMPLETED"))
        self.assertEqual(tuple(ChecklistState), ("PENDING", "PASS", "FAIL", "WAIVED"))

    def test_all_stage_pairs_only_five_adjacent_forward_pairs_valid(self):
        keys = tuple(stage.stage_key for stage in self.definition.stages)
        for i, current in enumerate(keys):
            for j, target in enumerate(keys):
                arguments = self.arguments | dict(current_stage_key=current, target_stage_key=target)
                with self.subTest(current=current, target=target):
                    if j == i + 1:
                        self.assertIsNone(validate_forward_structure(self.definition, **arguments))
                    else:
                        with self.assertRaises(WorkflowTransitionError):
                            validate_forward_structure(self.definition, **arguments)

    def test_not_started_completed_and_raw_state_rejected(self):
        for state in (WorkflowState.NOT_STARTED, WorkflowState.COMPLETED, "ACTIVE", None, True):
            with self.subTest(state=state), self.assertRaises(WorkflowTransitionError):
                validate_forward_structure(self.definition, **(self.arguments | dict(workflow_state=state)))

    def test_archived_project_and_malformed_archived_flag_rejected(self):
        for archived in (True, 0, 1, None, "false"):
            with self.subTest(archived=archived), self.assertRaises(WorkflowTransitionError):
                validate_forward_structure(self.definition, **(self.arguments | dict(project_archived=archived)))

    def test_optimistic_version_not_definition_version(self):
        validate_forward_structure(self.definition, **(self.arguments | dict(expected_version=19, lock_version=19)))
        for field in ("expected_version", "lock_version"):
            for value in (-1, True, "0", 0.0, None, 1):
                with self.subTest(field=field, value=value), self.assertRaises(WorkflowTransitionError):
                    validate_forward_structure(self.definition, **(self.arguments | {field: value}))

    def test_unknown_dynamic_and_non_string_keys_rejected(self):
        for field in ("current_stage_key", "target_stage_key"):
            for key in ("", "LATEST", "UNKNOWN", "handover", None, 1, []):
                with self.subTest(field=field, key=key), self.assertRaises(WorkflowTransitionError):
                    validate_forward_structure(self.definition, **(self.arguments | {field: key}))

    def test_adjacency_uses_sequence_not_arithmetic_order(self):
        definition = replace(self.definition, stages=tuple(
            replace(stage, order=stage.order * 10) for stage in self.definition.stages
        ))
        validate_forward_structure(definition, **self.arguments)
        with self.assertRaises(WorkflowTransitionError):
            validate_forward_structure(None, **self.arguments)

    def test_structure_check_does_not_mutate_or_claim_gate_pass(self):
        original = self.definition
        result = validate_forward_structure(original, **self.arguments)
        self.assertIsNone(result)
        self.assertIs(original, six_stage_definition())
        self.assertFalse(hasattr(original, "workflow_state"))


if __name__ == "__main__":
    unittest.main()
