from dataclasses import replace
import unittest

from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.definition import WorkflowDefinitionError
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.infrastructure.orm import (
    ProjectWorkflowRow, StageRow, StageChecklistRow, ChecklistItemRow,
)


class WorkflowPersistenceTests(unittest.TestCase):
    def test_fingerprint_is_frozen_and_covers_content(self):
        definition = six_stage_definition()
        self.assertEqual(definition_fingerprint(definition).hex(),
                         "4bcda512e4c0d26a9766bdb41d9086a73a6d187db61d319ff94a1e929c3802a9")
        for changed in (
            replace(definition, version=2),
            replace(definition, stages=(replace(definition.stages[0], gate_policy_ref="CHANGED"),) + definition.stages[1:]),
            replace(definition, stages=(replace(definition.stages[0], checklist_items=(
                replace(definition.stages[0].checklist_items[0], required=False),
                definition.stages[0].checklist_items[1],
            )),) + definition.stages[1:]),
        ):
            self.assertNotEqual(definition_fingerprint(definition), definition_fingerprint(changed))
        with self.assertRaises(WorkflowDefinitionError):
            definition_fingerprint(None)

    def test_four_tables_have_explicit_project_and_no_cascade(self):
        tables = tuple(row.__table__ for row in (
            ProjectWorkflowRow, StageRow, StageChecklistRow, ChecklistItemRow,
        ))
        self.assertEqual(tuple(table.name for table in tables), (
            "wfl_project_workflows", "wfl_stages", "wfl_stage_checklists", "wfl_checklist_items",
        ))
        for table in tables:
            self.assertEqual(table.schema, "plm")
            self.assertFalse(table.c.project_id.nullable)
            self.assertTrue(table.foreign_key_constraints)
            for constraint in table.foreign_key_constraints:
                self.assertEqual(constraint.ondelete, "NO ACTION")

    def test_orm_initial_states_are_not_approved_facts(self):
        self.assertEqual(str(ProjectWorkflowRow.__table__.c.workflow_state.server_default.arg), "'NOT_STARTED'")
        self.assertEqual(str(StageRow.__table__.c.stage_state.server_default.arg), "'NOT_STARTED'")
        self.assertEqual(str(ChecklistItemRow.__table__.c.item_state.server_default.arg), "'PENDING'")
