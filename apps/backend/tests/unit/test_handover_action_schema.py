from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.handover.infrastructure.orm import (
    HandoverActionEvidenceRefRow,
    HandoverActionItemRow,
    HandoverActionResponseRefRow,
    HandoverActionStateEventRow,
)


class HandoverActionFoundationSchemaTests(unittest.TestCase):
    def test_root_and_three_owned_tables_are_project_scoped(self):
        tables = (
            HandoverActionItemRow.__table__,
            HandoverActionResponseRefRow.__table__,
            HandoverActionEvidenceRefRow.__table__,
            HandoverActionStateEventRow.__table__,
        )
        self.assertEqual([
            "hnd_action_items", "hnd_action_response_refs",
            "hnd_action_evidence_refs", "hnd_action_state_events",
        ], [table.name for table in tables])
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual("plm", table.schema)
                self.assertIn("project_id", table.c)

    def test_source_response_evidence_and_event_constraints_exist(self):
        tables = (
            HandoverActionItemRow.__table__,
            HandoverActionResponseRefRow.__table__,
            HandoverActionEvidenceRefRow.__table__,
            HandoverActionStateEventRow.__table__,
        )
        names = {constraint.name for table in tables for constraint in table.constraints}
        for required in (
            "fk_hnd_actions__source_item",
            "fk_hnd_actions__resolution_trace",
            "fk_hnd_action_responses__document",
            "fk_hnd_action_evidence__evidence",
            "uq_hnd_action_events__action_sequence",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_lifecycle_and_allows_human_candidate_source(self):
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261005_0098_handover_action_foundation"
        )
        self.assertEqual("20261005_0097", migration.down_revision)
        for required in (
            "Handover Action Owner is not installed",
            "Handover Action lifecycle Owner is not installed",
            "Handover Action initial event is incomplete",
            "v.version_state='DRAFT' AND i.item_state='CANDIDATE'",
            "v.version_state='APPROVED' AND i.item_state='CONFIRMED'",
            "Handover Action history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self):
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261005_0098_handover_action_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Handover Action"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Handover Action history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )


if __name__ == "__main__":
    unittest.main()
