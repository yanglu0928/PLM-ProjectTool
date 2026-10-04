from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class HandoverReviewTerminalSchemaTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261005_0101_handover_review_terminal"
        )

    def test_transition_matrix_and_project_review_binding_are_narrow(self):
        self.assertEqual("20261005_0100", self.migration.down_revision)
        sql = (self.migration._REVIEW_OWNER_GUARD
               + self.migration._REVIEW_START_INTEGRITY
               + self.migration._TERMINAL_INTEGRITY)
        for required in (
            "OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'",
            "NEW.version_state IN ('APPROVED','RETURNED')",
            "OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'",
            "OLD.item_state<>'CANDIDATE' OR NEW.item_state<>'CONFIRMED'",
            "review_row.scope<>'PROJECT'",
            "review_row.subject_type<>'HND-02'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_action_coverage_and_terminal_projection_are_deferred(self):
        sql = (self.migration._REVIEW_START_INTEGRITY
               + self.migration._TERMINAL_INTEGRITY)
        for required in (
            "i.source_missing OR i.item_type='NEED_CONFIRM'",
            "a.source_kind='ANALYSIS_ITEM'",
            "a.action_state<>'CANCELLED'",
            "Handover Review requires active Action coverage",
            "i.item_state<>'CONFIRMED'",
            "Handover approval formalization is incomplete",
            "review_row.review_state NOT IN ('RETURNED','WITHDRAWN')",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_downgrade_is_offline_closed_and_preserves_review_history(self):
        with patch.object(
            self.migration.context, "is_offline_mode", return_value=True,
        ), patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(
                RuntimeError, "offline Handover Review",
            ):
                self.migration.downgrade()
        execute.assert_not_called()
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("Handover Review history prevents downgrade", source)
        self.assertIn("20261005_0097_handover_version_owner", source)


if __name__ == "__main__":
    unittest.main()
