from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.survey.infrastructure.orm import (
    SurveyConclusionEvidenceRefRow,
    SurveyConclusionOpenIssueRow,
    SurveyConclusionRow,
    SurveyDepartmentConclusionRow,
    SurveyModuleConclusionRow,
)


class SurveyConclusionFoundationSchemaTests(unittest.TestCase):
    def test_five_frozen_tables_are_project_scoped(self) -> None:
        tables = (
            SurveyConclusionRow.__table__, SurveyDepartmentConclusionRow.__table__,
            SurveyModuleConclusionRow.__table__,
            SurveyConclusionEvidenceRefRow.__table__,
            SurveyConclusionOpenIssueRow.__table__,
        )
        self.assertEqual(
            ["srv_conclusions", "srv_department_conclusions",
             "srv_module_conclusions", "srv_conclusion_evidence_refs",
             "srv_conclusion_open_issues"],
            [table.name for table in tables],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual("plm", table.schema)
                self.assertIn("project_id", table.c)

    def test_version_and_typed_reference_constraints_exist(self) -> None:
        tables = (
            SurveyConclusionRow.__table__, SurveyDepartmentConclusionRow.__table__,
            SurveyModuleConclusionRow.__table__,
            SurveyConclusionEvidenceRefRow.__table__,
            SurveyConclusionOpenIssueRow.__table__,
        )
        names = {constraint.name for table in tables for constraint in table.constraints}
        for required in (
            "uq_srv_conclusions__series_no", "fk_srv_conclusions__supersedes",
            "fk_srv_conclusions__survey", "ck_srv_conclusions__refs",
            "fk_srv_department_conclusions__version",
            "ck_srv_department_conclusions__decision",
            "fk_srv_module_conclusions__version",
            "ck_srv_module_conclusions__decision",
            "fk_srv_conclusion_evidence__document",
            "ck_srv_conclusion_evidence__role",
            "fk_srv_conclusion_issues__handover_action",
            "ck_srv_conclusion_issues__type",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_unowned_writes_and_snapshots(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0109_survey_conclusion_foundation"
        )
        self.assertEqual("20261006_0108", migration.down_revision)
        for required in (
            "Survey Conclusion history is immutable",
            "Survey Conclusion initial state is invalid",
            "Survey Conclusion supersedes chain is invalid",
            "Survey Conclusion requires closed matching Rounds",
            "Survey Conclusion AI provenance is invalid",
            "Survey Conclusion Response snapshot is invalid",
            "Survey Conclusion Evidence snapshot is invalid",
            "Survey Conclusion open issue snapshot is invalid",
            "Survey Conclusion declared collections mismatch",
            "Survey Conclusion history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0109_survey_conclusion_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Survey Conclusion"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Survey Conclusion history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )


if __name__ == "__main__":
    unittest.main()
