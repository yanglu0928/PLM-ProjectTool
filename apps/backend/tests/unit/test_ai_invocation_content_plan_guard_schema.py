from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch


class AIInvocationContentPlanGuardSchemaTests(unittest.TestCase):
    def test_guard_covers_task_snapshot_plan_and_payload_identity(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0073_ai_invocation_content_plan_guard"
        )
        source = migration._GUARD
        for required in (
            "NEW.content_plan_ref IS NULL",
            "task_row.content_plan_ref",
            "snapshot_row.content_plan_ref",
            "snapshot_row.preview_payload_fingerprint",
            "plan_row.task_parameters_fingerprint",
            "plan_row.context_bundle_fingerprint",
            "plan_row.payload_fingerprint",
        ):
            self.assertIn(required, source)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0073_ai_invocation_content_plan_guard"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline AI Invocation"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
