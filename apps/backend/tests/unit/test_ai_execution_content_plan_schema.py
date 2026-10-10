from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from sqlalchemy import inspect

from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIExecutionContentPlanRow,
    AIExecutionContentSourceRow,
)
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow,
    AIInvocationRow,
    AITaskRow,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIEgressAuthorizationRow,
)


class AIExecutionContentPlanSchemaTests(unittest.TestCase):
    def test_orm_exposes_no_content_or_locator_and_all_chain_references(self) -> None:
        plan = inspect(AIExecutionContentPlanRow)
        source = inspect(AIExecutionContentSourceRow)
        forbidden = {"content", "prompt_text", "task_parameters", "storage_locator",
                     "provider_secret", "provider_response"}
        self.assertFalse(forbidden & set(plan.columns.keys()))
        self.assertFalse(forbidden & set(source.columns.keys()))
        self.assertEqual(
            {"source_fingerprint", "content_fingerprint", "projection_fingerprint"},
            {name for name in source.columns.keys() if name.endswith("fingerprint")},
        )
        for row_type in (
            AIEgressAuthorizationRow, AITaskRow,
            AIEgressAuthorizationSnapshotRow, AIInvocationRow,
        ):
            self.assertIn("content_plan_ref", inspect(row_type).columns.keys())

    def test_plan_and_source_constraints_are_declared_in_metadata(self) -> None:
        plan_table = AIExecutionContentPlanRow.__table__
        source_table = AIExecutionContentSourceRow.__table__
        plan_constraints = {item.name for item in plan_table.constraints}
        source_constraints = {item.name for item in source_table.constraints}
        self.assertIn("uq_ai_content_plans__preview", plan_constraints)
        self.assertIn("ck_ai_content_plans__context", plan_constraints)
        self.assertIn("uq_ai_content_sources__ordinal", source_constraints)
        self.assertIn("uq_ai_content_sources__semantic", source_constraints)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0072_ai_execution_content_plan"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline AI Content Plan"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
