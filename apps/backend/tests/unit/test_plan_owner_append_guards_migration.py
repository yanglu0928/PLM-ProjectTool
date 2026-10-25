from __future__ import annotations

import importlib
import inspect
import unittest


class PlanOwnerAppendGuardsMigrationTests(unittest.TestCase):
    def test_migration_changes_only_owner_guard_functions(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0188_plan_owner_append_guards")
        self.assertEqual(migration.down_revision, "20261026_0187")
        self.assertEqual(len(migration._OWNER_FUNCTIONS), 8)
        source = inspect.getsource(migration._install_append_only_guards)
        self.assertIn("TG_OP = 'INSERT'", source)
        self.assertIn("snapshots are immutable", source)
        self.assertNotIn("DROP TRIGGER", source)
        self.assertNotIn("DROP TABLE", source)

    def test_downgrade_restores_closed_guards_without_dropping_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0188_plan_owner_append_guards")
        source = inspect.getsource(migration.downgrade)
        restore = inspect.getsource(migration._restore_closed_guards)
        self.assertIn("_restore_closed_guards()", source)
        self.assertIn("Owner is not installed", restore)
        self.assertNotIn("DROP TABLE", restore)
        self.assertNotIn("TRUNCATE", restore)


if __name__ == "__main__":
    unittest.main()
