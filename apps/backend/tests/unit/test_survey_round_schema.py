from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.survey.infrastructure.orm import (
    SurveyRoundRow,
    SurveyRoundSourceRecordRow,
)


class SurveyRoundFoundationSchemaTests(unittest.TestCase):
    def test_round_and_source_tables_are_project_scoped(self) -> None:
        tables = (SurveyRoundRow.__table__, SurveyRoundSourceRecordRow.__table__)
        self.assertEqual(
            ["srv_rounds", "srv_round_source_records"],
            [table.name for table in tables],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual("plm", table.schema)
                self.assertIn("project_id", table.c)
                self.assertIn("survey_id", table.c)
                self.assertIn("survey_version_id", table.c)

    def test_identity_append_only_and_snapshot_constraints_exist(self) -> None:
        tables = (SurveyRoundRow.__table__, SurveyRoundSourceRecordRow.__table__)
        names = {constraint.name for table in tables for constraint in table.constraints}
        for required in (
            "uq_srv_rounds__identity",
            "uq_srv_rounds__survey_no",
            "fk_srv_rounds__version",
            "ck_srv_rounds__lifecycle",
            "fk_srv_round_sources__round",
            "fk_srv_round_sources__question",
            "fk_srv_round_sources__document",
            "fk_srv_round_sources__evidence",
            "uq_srv_round_sources__round_question_evidence",
            "ck_srv_round_sources__fingerprint",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_round_and_source_ownership(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0107_survey_round_foundation"
        )
        self.assertEqual("20261006_0106", migration.down_revision)
        for required in (
            "Survey Round requires the current approved definition",
            "Survey Round state transition is invalid",
            "Survey Round source record is immutable",
            "Survey Round source requires an open matching Round",
            "Survey Round source is not an eligible PROJECT_RECORD",
            "Survey Round history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0107_survey_round_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Survey Round"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Survey Round history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )


if __name__ == "__main__":
    unittest.main()
