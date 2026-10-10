from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class HandoverActionMetadataSchemaTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0100_handover_action_metadata"
        )

    def test_only_open_or_in_progress_same_state_event_is_added(self):
        self.assertEqual("20261005_0099", self.migration.down_revision)
        self.assertIn(
            "OLD.action_state=NEW.action_state AND OLD.action_state IN ('OPEN','IN_PROGRESS')",
            self.migration._GUARDS,
        )
        self.assertIn(
            "NEW.from_state=NEW.to_state AND NEW.from_state IN ('OPEN','IN_PROGRESS')",
            self.migration._GUARDS,
        )
        self.assertIn("Handover Action metadata change is empty", self.migration._GUARDS)

    def test_identity_and_lifecycle_fields_remain_immutable(self):
        for field in (
            "NEW.source_analysis_version_ref", "NEW.source_item_id",
            "NEW.action_type", "NEW.created_by", "NEW.created_reason",
        ):
            self.assertIn(field, self.migration._GUARDS)

    def test_downgrade_preserves_same_state_history(self):
        with patch.object(self.migration.context, "is_offline_mode", return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Handover Action metadata"):
                self.migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Handover Action metadata history prevents downgrade",
            inspect.getsource(self.migration.downgrade),
        )


if __name__ == "__main__":
    unittest.main()
