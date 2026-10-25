from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanRow


class PlanIdentitySchemaTests(unittest.TestCase):
    def test_identity_and_versioned_approved_pointer(self) -> None:
        table = PlanRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_plans"))
        self.assertTrue(table.c.current_approved_version_ref.nullable)
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"uq_pln_plans__id_project", "fk_pln_plans__project",
                         "fk_pln_plans__creator"} <= names)
        self.assertNotIn("ck_pln_plans__approved_pointer_closed", names)

    def test_migration_chain_and_history_guard(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0167_plan_identity_foundation")
        self.assertEqual(migration.down_revision, "20261019_0166")
        self.assertIn("Plan identity Owner is not installed", migration._GUARDS)
        self.assertIn("Plan identity history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Plan identity downgrade"):
                migration.downgrade()
        self.assertIn("Plan identity history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
