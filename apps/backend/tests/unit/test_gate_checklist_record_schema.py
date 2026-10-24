import importlib
import unittest

from plm_assistant.modules.workflow.infrastructure.history_orm import TransitionGateItemRow


class GateChecklistRecordSchemaTests(unittest.TestCase):
    def test_legacy_nullable_fields_but_composite_no_cascade_fk(self):
        table = TransitionGateItemRow.__table__
        for name in ("checklist_record_id", "observed_item_version", "record_fingerprint"):
            self.assertTrue(table.c[name].nullable)
            self.assertIsNone(table.c[name].server_default)
        fk = next(fk for fk in table.foreign_key_constraints if fk.name == "fk_wfl_gate_items__record")
        self.assertEqual(tuple(fk.column_keys), ("checklist_record_id", "workflow_id", "project_id", "item_key"))
        self.assertEqual(fk.ondelete, "NO ACTION")

    def test_migration_independent_and_requires_new_current_committed_link(self):
        module = importlib.import_module("plm_assistant.migrations.versions.20260926_0033_gate_checklist_record")
        self.assertEqual(module.down_revision, "20260926_0032")
        for required in ("New Gate requires fixed Checklist record", "r.created_xid=txid_current()",
                         "Gate Checklist record stale", "Gate fixed basis identity set mismatch",
                         "Gate basis observation regressed", "Gate waiver fixed details mismatch"):
            self.assertIn(required, module._GUARDS)
        self.assertIn("observed_item_version IS NOT NULL", module._SHAPE)
