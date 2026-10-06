from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class SurveyStateSchemaTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261006_0106_survey_state_owner"
        )

    def test_only_metadata_and_one_way_archive_are_opened(self):
        sql = self.migration._STATE_OWNER_GUARD
        self.assertEqual("20261006_0105", self.migration.down_revision)
        for required in (
            "OLD.survey_state='ACTIVE' AND NEW.survey_state='ACTIVE'",
            "NEW.name IS DISTINCT FROM OLD.name",
            "v.version_state='IN_REVIEW'",
            "OLD.survey_state='ACTIVE' AND NEW.survey_state='ARCHIVED'",
            "Survey state transition is invalid",
            "OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'",
            "OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)
        self.assertNotIn("OLD.survey_state='ARCHIVED' AND NEW.survey_state='ACTIVE'", sql)

    def test_downgrade_is_offline_closed_and_preserves_state_history(self):
        with patch.object(
            self.migration.context, "is_offline_mode", return_value=True,
        ), patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "state-owner downgrade"):
                self.migration.downgrade()
        execute.assert_not_called()
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("Survey state-owner history prevents downgrade", source)
        self.assertIn("20261006_0105_survey_review_terminal", source)


if __name__ == "__main__":
    unittest.main()
