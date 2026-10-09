from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.solution.infrastructure.orm import (
    GlobalReferencePublicationEventRow,
)


class GlobalReferencePublicationSchemaTests(unittest.TestCase):
    def test_closed_version_bound_event_contract(self) -> None:
        table = GlobalReferencePublicationEventRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(table.name, "sol_global_reference_publication_events")
        self.assertEqual(tuple(column.name for column in table.primary_key.columns),
                         ("publication_event_id",))
        self.assertTrue({
            "uq_sol_global_publications__root_no",
            "fk_sol_global_publications__version",
            "fk_sol_global_publications__actor",
            "ck_sol_global_publications__scope",
            "ck_sol_global_publications__kind",
            "ck_sol_global_publications__label",
        } <= {constraint.name for constraint in table.constraints})

    def test_migration_preserves_closed_guard_and_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261009_0157_global_reference_publication_closed")
        self.assertEqual(migration.down_revision, "20261009_0156")
        self.assertIn("Owner is not installed", migration._GUARD)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline GLOBAL Reference publication"):
                migration.downgrade()
        self.assertIn("history prevents downgrade", inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
