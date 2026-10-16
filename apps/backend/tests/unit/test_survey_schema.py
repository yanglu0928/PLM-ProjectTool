from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.survey.infrastructure.orm import (
    SurveyQuestionOptionRow,
    SurveyQuestionRow,
    SurveyQuestionSourceRefRow,
    SurveyRow,
    SurveyTargetDepartmentRow,
    SurveyVersionRow,
)


class SurveyDefinitionFoundationSchemaTests(unittest.TestCase):
    def test_two_roots_and_four_owned_tables_are_project_scoped(self) -> None:
        tables = (
            SurveyRow.__table__, SurveyVersionRow.__table__,
            SurveyQuestionRow.__table__, SurveyQuestionOptionRow.__table__,
            SurveyQuestionSourceRefRow.__table__, SurveyTargetDepartmentRow.__table__,
        )
        self.assertEqual(
            ["srv_surveys", "srv_survey_versions", "srv_questions",
             "srv_question_options", "srv_question_source_refs",
             "srv_target_departments"],
            [table.name for table in tables],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual("plm", table.schema)
                self.assertIn("project_id", table.c)

    def test_frozen_identity_question_source_and_target_constraints_exist(self) -> None:
        tables = (
            SurveyRow.__table__, SurveyVersionRow.__table__,
            SurveyQuestionRow.__table__, SurveyQuestionOptionRow.__table__,
            SurveyQuestionSourceRefRow.__table__, SurveyTargetDepartmentRow.__table__,
        )
        names = {constraint.name for table in tables for constraint in table.constraints}
        for required in (
            "fk_srv_surveys__approved_version",
            "uq_srv_versions__survey_no",
            "uq_srv_questions__version_stable",
            "fk_srv_options__question",
            "fk_srv_question_sources__handover_item",
            "fk_srv_question_sources__capability_item",
            "fk_srv_question_sources__template_version",
            "fk_srv_targets__department",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_owner_and_checks_source_semantics(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0103_survey_definition_foundation"
        )
        self.assertEqual("20261005_0102", migration.down_revision)
        for required in (
            "Survey definition Owner is not installed",
            "SurveyVersion declared counts are incomplete",
            "Survey question requires a source",
            "Survey choice options are incomplete",
            "Survey Handover source is not a current approved project item",
            "Survey Capability source is not a current approved item",
            "d.document_category='TEMPLATE'",
            "Survey target department is not active in the project",
            "Survey definition history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0103_survey_definition_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Survey definition"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn("Survey definition history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
