from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.handover.infrastructure.orm import (
    HandoverAITaskRefRow,
    HandoverAnalysisItemRow,
    HandoverAnalysisRow,
    HandoverAnalysisVersionRow,
    HandoverItemCapabilityRefRow,
    HandoverItemEvidenceRefRow,
    HandoverItemOptionRow,
    HandoverSourceDocumentRefRow,
)


class HandoverAnalysisFoundationSchemaTests(unittest.TestCase):
    def test_two_roots_and_six_owned_tables_are_project_scoped(self):
        tables = (
            HandoverAnalysisRow.__table__, HandoverAnalysisVersionRow.__table__,
            HandoverSourceDocumentRefRow.__table__, HandoverAITaskRefRow.__table__,
            HandoverAnalysisItemRow.__table__, HandoverItemEvidenceRefRow.__table__,
            HandoverItemCapabilityRefRow.__table__, HandoverItemOptionRow.__table__,
        )
        self.assertEqual([
            "hnd_analyses", "hnd_analysis_versions",
            "hnd_analysis_source_document_refs", "hnd_analysis_ai_task_refs",
            "hnd_analysis_items", "hnd_item_evidence_refs",
            "hnd_item_capability_refs", "hnd_item_options",
        ], [table.name for table in tables])
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual("plm", table.schema)
                self.assertIn("project_id", table.c)

    def test_fixed_source_and_item_constraints_exist(self):
        tables = (
            HandoverAnalysisRow.__table__, HandoverAnalysisVersionRow.__table__,
            HandoverSourceDocumentRefRow.__table__, HandoverAITaskRefRow.__table__,
            HandoverAnalysisItemRow.__table__, HandoverItemEvidenceRefRow.__table__,
            HandoverItemCapabilityRefRow.__table__, HandoverItemOptionRow.__table__,
        )
        names = {constraint.name for table in tables for constraint in table.constraints}
        for required in (
            "fk_hnd_analyses__approved_version",
            "fk_hnd_versions__capability_version",
            "fk_hnd_source_docs__document_version",
            "fk_hnd_ai_refs__task",
            "uq_hnd_items__version_stable",
            "fk_hnd_item_evidence__evidence",
            "fk_hnd_item_capability__capability",
            "uq_hnd_item_options__item_code",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_owner_and_checks_formal_inputs(self):
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0096_handover_analysis_foundation"
        )
        self.assertEqual("20261005_0095", migration.down_revision)
        for required in (
            "Handover Analysis Owner is not installed",
            "Handover AnalysisVersion declared counts are incomplete",
            "handover-source-set.v1",
            "Handover requires an approved Capability baseline version",
            "Handover AnalysisItem requires evidence or missing-source declaration",
            "Handover NEED_CONFIRM prompt is incomplete",
            "t.task_type<>'GAP_ANALYSIS'",
            "Handover analysis history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self):
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0096_handover_analysis_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Handover"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn("Handover analysis history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
