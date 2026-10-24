from __future__ import annotations

import importlib
import unittest


migration = importlib.import_module(
    "plm_assistant.migrations.versions.20261006_0105_survey_review_terminal"
)


class SurveyReviewSchemaTests(unittest.TestCase):
    def test_revision_extends_survey_version_owner(self) -> None:
        self.assertEqual(migration.revision, "20261006_0105")
        self.assertEqual(migration.down_revision, "20261006_0104")

    def test_review_owner_allows_only_three_version_paths(self) -> None:
        sql = migration._REVIEW_OWNER_GUARD
        self.assertIn("OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'", sql)
        self.assertIn("NEW.version_state IN ('APPROVED','RETURNED')", sql)
        self.assertIn("OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'", sql)
        self.assertIn("NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref", sql)
        self.assertIn("NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref", sql)
        self.assertIn("SurveyVersion update is outside Review Owner", sql)

    def test_review_bindings_are_project_scoped_and_policy_locked(self) -> None:
        for sql in (
            migration._REVIEW_START_INTEGRITY,
            migration._TERMINAL_INTEGRITY,
        ):
            self.assertIn("review_row.scope<>'PROJECT'", sql)
            self.assertIn("review_row.subject_type<>'SRV-02'", sql)
            self.assertIn("review_row.policy_code<>'SURVEY_ALL_V1'", sql)
            self.assertIn("round_row.subject_version_id", sql)

    def test_terminal_integrity_requires_pointer_convergence(self) -> None:
        sql = migration._TERMINAL_INTEGRITY
        self.assertIn("current_approved_version_ref", sql)
        self.assertIn("Survey approval formalization is incomplete", sql)
        self.assertIn("Survey nonapproval formalization is invalid", sql)
        self.assertIn("Survey superseded version is invalid", sql)

    def test_downgrade_refuses_review_history(self) -> None:
        source = importlib.util.find_spec(migration.__name__)
        self.assertIsNotNone(source)
        sql = migration.__loader__.get_source(migration.__name__)
        self.assertIn("Survey Review history prevents downgrade", sql)
        self.assertIn("20261006_0104_survey_version_owner", sql)


if __name__ == "__main__":
    unittest.main()
