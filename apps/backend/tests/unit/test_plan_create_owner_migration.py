from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class PlanCreateOwnerMigrationTests(unittest.TestCase):
    def test_sequential_atomic_insert_only(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0169_plan_identity_create_owner")
        self.assertEqual(migration.down_revision, "20261019_0168")
        self.assertIn("Plan create result is required", migration._OPEN_ROOT)
        self.assertIn("DEFERRABLE INITIALLY DEFERRED", inspect.getsource(migration.upgrade))
        self.assertIn("Plan create result operation is not installed", migration._OPEN_RESULT)
        self.assertIn("Plan history prevents create Owner downgrade",
                      inspect.getsource(migration.downgrade))
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Plan create Owner downgrade"):
                migration.downgrade()


if __name__ == "__main__":
    unittest.main()
