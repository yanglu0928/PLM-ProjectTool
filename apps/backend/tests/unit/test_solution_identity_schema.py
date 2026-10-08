from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.solution.infrastructure.orm import SolutionOutlineRow, SolutionSectionRow


class SolutionIdentitySchemaTests(unittest.TestCase):
    def test_frozen_identity_names_and_project_constraints(self) -> None:
        outline = SolutionOutlineRow.__table__
        section = SolutionSectionRow.__table__
        self.assertEqual((outline.schema, outline.name), ("plm", "sol_outlines"))
        self.assertEqual((section.schema, section.name), ("plm", "sol_sections"))
        for table in (outline, section):
            self.assertIn("project_id", table.c)
            self.assertTrue(table.c.current_approved_version_ref.nullable)
        names = {constraint.name for table in (outline, section) for constraint in table.constraints}
        self.assertTrue({"uq_sol_outlines__id_project", "fk_sol_outlines__project",
                         "uq_sol_sections__outline_key", "fk_sol_sections__outline_project"} <= names)

    def test_migration_is_sequential_and_fail_closed(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261008_0136_solution_identity_foundation")
        self.assertEqual(migration.down_revision, "20261008_0135")
        self.assertIn("Solution identity Owner is not installed", migration._GUARDS)
        self.assertIn("Solution identity history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Solution identity downgrade"):
                migration.downgrade()
        self.assertIn("Solution identity history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
