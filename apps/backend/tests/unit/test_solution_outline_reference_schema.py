from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.solution.infrastructure.orm import (
    ReferenceSolutionVersionRow,
    SolutionOutlineReferenceRefRow,
    SolutionOutlineVersionRow,
)


class SolutionOutlineReferenceSchemaTests(unittest.TestCase):
    def test_fixed_reference_link_is_project_bounded(self) -> None:
        version = SolutionOutlineVersionRow.__table__
        ref = SolutionOutlineReferenceRefRow.__table__
        source = ReferenceSolutionVersionRow.__table__
        self.assertEqual(ref.schema, "plm")
        self.assertEqual(ref.c.source_project_id.nullable, True)
        self.assertEqual(version.c.declared_reference_count.server_default.arg.text, "0")
        names = {constraint.name for table in (version, ref, source)
                 for constraint in table.constraints}
        self.assertTrue({
            "ck_sol_outline_versions__reference_count",
            "uq_sol_reference_versions__id_parent_scope_project",
            "fk_sol_outline_references__version",
            "fk_sol_outline_references__reference",
            "fk_sol_outline_references__project_source",
            "ck_sol_outline_references__scope_project",
            "uq_sol_outline_references__version_ordinal",
            "uq_sol_outline_references__version_reference",
        } <= names)

    def test_migration_stays_closed_and_refuses_history_loss(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261009_0154_outline_reference_link_closed")
        self.assertEqual(migration.down_revision, "20261009_0153")
        upgrade = inspect.getsource(migration.upgrade)
        downgrade = inspect.getsource(migration.downgrade)
        self.assertIn("guard_solution_outline_version_foundation", upgrade)
        self.assertIn("reject_solution_outline_version_truncate", upgrade)
        self.assertIn("Outline reference history prevents downgrade", downgrade)
        self.assertIn("Outline reference count history prevents downgrade", downgrade)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Outline reference downgrade"):
                migration.downgrade()


if __name__ == "__main__":
    unittest.main()
