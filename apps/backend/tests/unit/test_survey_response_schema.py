from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.survey.infrastructure.orm import (
    SurveyAnswerEvidenceRefRow,
    SurveyAnswerRow,
    SurveyAssignmentRow,
    SurveyResponseRow,
)


class SurveyResponseFoundationSchemaTests(unittest.TestCase):
    def test_four_frozen_tables_are_project_scoped(self) -> None:
        tables = (
            SurveyAssignmentRow.__table__, SurveyResponseRow.__table__,
            SurveyAnswerRow.__table__, SurveyAnswerEvidenceRefRow.__table__,
        )
        self.assertEqual(
            ["srv_assignments", "srv_responses", "srv_answers",
             "srv_answer_evidence_refs"],
            [table.name for table in tables],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual("plm", table.schema)
                self.assertIn("project_id", table.c)

    def test_target_chain_and_snapshot_constraints_exist(self) -> None:
        tables = (
            SurveyAssignmentRow.__table__, SurveyResponseRow.__table__,
            SurveyAnswerRow.__table__, SurveyAnswerEvidenceRefRow.__table__,
        )
        names = {constraint.name for table in tables for constraint in table.constraints}
        for required in (
            "uq_srv_assignments__round_target", "fk_srv_assignments__round",
            "fk_srv_assignments__target", "uq_srv_responses__question_chain",
            "uq_srv_responses__correction_successor",
            "fk_srv_responses__assignment", "fk_srv_responses__round_source",
            "uq_srv_answers__response", "fk_srv_answers__response",
            "fk_srv_answer_evidence__answer",
            "fk_srv_answer_evidence__document",
            "ck_srv_answer_evidence__fingerprint",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_response_ownership(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0108_survey_response_foundation"
        )
        self.assertEqual("20261006_0107", migration.down_revision)
        for required in (
            "Survey Assignment requires an open matching Round target",
            "Survey Assignment assignee is not an active target member",
            "Survey Assignment state transition is invalid",
            "Survey Response history is immutable",
            "Survey Response correction chain is invalid",
            "Facilitated Survey Response source is invalid",
            "Survey Answer Evidence snapshot is invalid",
            "Survey Response requires exactly one Answer",
            "Survey Response history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0108_survey_response_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Survey Response"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Survey Response history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )


if __name__ == "__main__":
    unittest.main()
