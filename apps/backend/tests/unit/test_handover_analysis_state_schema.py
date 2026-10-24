from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class HandoverAnalysisStateSchemaTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261005_0102_handover_analysis_state_owner"
        )

    def test_only_metadata_and_one_way_archive_are_opened(self):
        sql = self.migration._STATE_OWNER_GUARD
        self.assertEqual("20261005_0101", self.migration.down_revision)
        for required in (
            "OLD.analysis_state='ACTIVE' AND NEW.analysis_state='ACTIVE'",
            "NEW.analysis_purpose IS DISTINCT FROM OLD.analysis_purpose",
            "v.version_state='IN_REVIEW'",
            "OLD.analysis_state='ACTIVE' AND NEW.analysis_state='ARCHIVED'",
            "Handover Analysis state transition is invalid",
            "OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'",
            "OLD.item_state<>'CANDIDATE' OR NEW.item_state<>'CONFIRMED'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)
        self.assertNotIn("NEW.source_set_ref IS DISTINCT FROM OLD.source_set_ref\n+       AND", sql)

    def test_downgrade_is_offline_closed_and_preserves_state_history(self):
        with patch.object(
            self.migration.context, "is_offline_mode", return_value=True,
        ), patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "state-owner downgrade"):
                self.migration.downgrade()
        execute.assert_not_called()
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("Handover Analysis state-owner history prevents downgrade", source)
        self.assertIn("20261005_0101_handover_review_terminal", source)


if __name__ == "__main__":
    unittest.main()
