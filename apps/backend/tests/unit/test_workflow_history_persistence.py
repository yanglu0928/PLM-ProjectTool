import importlib
import unittest

from plm_assistant.modules.workflow.infrastructure.history_orm import (
    StageTransitionRow, TransitionGateItemRow, TransitionGateRefRow,
)


class WorkflowHistoryPersistenceTests(unittest.TestCase):
    def test_exact_table_names_and_no_mutable_lock_fields(self):
        for row, name in ((StageTransitionRow, "wfl_stage_transitions"),
                          (TransitionGateItemRow, "wfl_transition_gate_items"),
                          (TransitionGateRefRow, "wfl_transition_gate_refs")):
            self.assertEqual(row.__table__.fullname, "plm." + name)
            self.assertNotIn("updated_at", row.__table__.c)
            self.assertNotIn("lock_version", row.__table__.c)

    def test_foreign_keys_no_cascade_and_evidence_computed(self):
        for row in (StageTransitionRow, TransitionGateItemRow, TransitionGateRefRow):
            for fk in row.__table__.foreign_key_constraints:
                self.assertEqual(fk.ondelete, "NO ACTION")
        evidence = TransitionGateRefRow.__table__.c.evidence_id
        self.assertTrue(evidence.computed.persisted)
        self.assertIn("ref_kind='EVIDENCE'", str(evidence.computed.sqltext))

    def test_migration_is_self_contained_and_has_append_and_deferred_guards(self):
        module = importlib.import_module(
            "plm_assistant.migrations.versions.20260926_0031_workflow_history")
        self.assertEqual(module.down_revision, "20260926_0030")
        self.assertEqual(len(module._TABLES), 3)
        self.assertIn("root.created_xid<>txid_current()", module._GUARDS)
        self.assertIn("Workflow history/state atomicity invalid", module._GUARDS)
        self.assertIn("Workflow Evidence facts changed before commit", module._GUARDS)
