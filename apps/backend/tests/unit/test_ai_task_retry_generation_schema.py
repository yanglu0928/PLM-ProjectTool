from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from plm_assistant.modules.ai.infrastructure.task_orm import AITaskRetryGenerationRow


class AITaskRetryGenerationSchemaTests(unittest.TestCase):
    def test_lineage_is_owned_immutable_and_bounded(self) -> None:
        table = AITaskRetryGenerationRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual([column.name for column in table.primary_key.columns],
                         ["new_ai_task_id"])
        self.assertTrue(all(not column.nullable for column in table.c))
        self.assertEqual(len(table.foreign_key_constraints), 7)
        self.assertTrue(any(
            constraint.name == "uq_ai_task_retries__new_job"
            for constraint in table.constraints
        ))
        self.assertTrue(any(
            constraint.name == "uq_ai_task_retries__root_generation"
            for constraint in table.constraints
        ))

    def test_guard_requires_terminal_source_exact_snapshots_and_audit(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0075_ai_task_retry_generation"
        )
        for required in (
            "source_task.task_state NOT IN ('FAILED','CANCELLED')",
            "source_task.retryable IS DISTINCT FROM TRUE",
            "AI Task retry input snapshot drifted",
            "AI Task retry egress snapshot drifted or limit exceeded",
            "AI_TASK_USER_RETRY_REQUESTED",
            "history cannot be truncated",
        ):
            self.assertIn(required, migration._GUARDS)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0075_ai_task_retry_generation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline AI Task retry"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
