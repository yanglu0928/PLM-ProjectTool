import importlib
import unittest

from plm_assistant.modules.workflow.infrastructure.checklist_record_orm import (
    ChecklistRecordRow, ChecklistRecordRefRow,
)


class ChecklistRecordPersistenceTests(unittest.TestCase):
    def test_owned_tables_and_separate_immutable_version_sequences(self):
        self.assertEqual(ChecklistRecordRow.__table__.fullname, "plm.wfl_checklist_records")
        self.assertEqual(ChecklistRecordRefRow.__table__.fullname, "plm.wfl_checklist_record_refs")
        columns = ChecklistRecordRow.__table__.c
        for column in ("before_item_version", "after_item_version",
                       "before_workflow_version", "after_workflow_version", "supersedes_record_id"):
            self.assertIn(column, columns)
        for column in ("updated_at", "lock_version"):
            self.assertNotIn(column, columns)

    def test_no_cascade_compound_parent_and_generated_evidence_fk(self):
        for row in (ChecklistRecordRow, ChecklistRecordRefRow):
            for fk in row.__table__.foreign_key_constraints:
                self.assertEqual(fk.ondelete, "NO ACTION")
        parent = next(fk for fk in ChecklistRecordRefRow.__table__.foreign_key_constraints
                      if fk.name == "fk_wfl_record_refs__record")
        self.assertEqual(tuple(parent.column_keys), ("record_id", "workflow_id", "project_id", "item_key"))
        self.assertTrue(ChecklistRecordRefRow.__table__.c.evidence_id.computed.persisted)

    def test_independent_frozen_migration_guards_missing_chain_and_atomicity(self):
        module = importlib.import_module("plm_assistant.migrations.versions.20260926_0032_checklist_records")
        self.assertEqual(module.down_revision, "20260926_0031")
        self.assertEqual(len(module._TABLES), 2)
        for expected in ("Checklist trusted previous record missing",
                         "Checklist history/projection atomicity invalid", "root.created_xid<>txid_current()",
                         "Checklist Evidence facts changed before commit"):
            self.assertIn(expected, module._GUARDS)
