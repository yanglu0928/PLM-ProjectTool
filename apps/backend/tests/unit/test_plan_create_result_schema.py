from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanCreateResultRow


class PlanCreateResultSchemaTests(unittest.TestCase):
    def test_snapshot_identity_and_constraints(self) -> None:
        table = PlanCreateResultRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_plan_create_results"))
        names = {item.name for item in table.constraints}
        self.assertTrue({"fk_pln_plan_create_results__plan",
                         "ck_pln_plan_create_results__name",
                         "ck_pln_plan_create_results__created_at"} <= names)

    def test_migration_chain_and_closed_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0168_plan_create_result")
        self.assertEqual(migration.down_revision, "20261019_0167")
        self.assertIn("Plan create result Owner is not installed", migration._GUARDS)
        self.assertIn("Plan create result history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Plan create result downgrade"):
                migration.downgrade()
        self.assertIn("Plan create result history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
