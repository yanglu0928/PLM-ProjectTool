from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.solution.infrastructure.orm import (
    SolutionOutlineVersionCreateResultRow,
)


class OutlineVersionResultSchemaTests(unittest.TestCase):
    def test_closed_first_response_table_contract(self) -> None:
        table = SolutionOutlineVersionCreateResultRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(table.name, "sol_outline_version_create_results")
        self.assertEqual(tuple(column.name for column in table.primary_key.columns),
                         ("solution_outline_version_id",))
        self.assertTrue({
            "fk_sol_outline_version_results__version",
            "fk_sol_outline_version_results__actor",
            "ck_sol_outline_version_results__fingerprint",
            "ck_sol_outline_version_results__declarations",
            "ck_sol_outline_version_results__counts",
        } <= {constraint.name for constraint in table.constraints})

    def test_migration_preserves_closed_guard_and_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261009_0155_outline_version_first_result_closed")
        self.assertEqual(migration.down_revision, "20261009_0154")
        self.assertIn("Owner is not installed", migration._GUARDS)
        self.assertIn("history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline OutlineVersion create result"):
                migration.downgrade()
        self.assertIn("history prevents downgrade", inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
