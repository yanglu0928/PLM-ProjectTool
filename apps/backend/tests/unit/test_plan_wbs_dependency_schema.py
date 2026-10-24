from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanWbsDependencyRow


class PlanWbsDependencySchemaTests(unittest.TestCase):
    def test_two_ends_same_version_and_fs_constraints(self) -> None:
        table = PlanWbsDependencyRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_wbs_dependencies"))
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"uq_pln_wbs_deps__version_edge", "fk_pln_wbs_deps__version",
                         "fk_pln_wbs_deps__predecessor", "fk_pln_wbs_deps__successor",
                         "ck_pln_wbs_deps__type", "ck_pln_wbs_deps__not_self",
                         "ck_pln_wbs_deps__lag_explicit"} <= names)
        self.assertTrue({"ix_pln_wbs_deps__out", "ix_pln_wbs_deps__in"}
                        <= {index.name for index in table.indexes})

    def test_migration_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0172_wbs_fs_dependency_foundation")
        self.assertEqual(migration.down_revision, "20261019_0171")
        self.assertIn("WbsDependency Owner is not installed", migration._GUARDS)
        self.assertIn("WbsDependency history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline WbsDependency downgrade"):
                migration.downgrade()
        self.assertIn("WbsDependency history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
