from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.solution.infrastructure.orm import (
    SolutionOutlineRequirementRefRow,
    SolutionOutlineSectionRow,
    SolutionOutlineVersionRow,
    SolutionSectionRow,
)


class SolutionOutlineVersionSchemaTests(unittest.TestCase):
    def test_project_scoped_version_and_fixed_references(self) -> None:
        version = SolutionOutlineVersionRow.__table__
        sections = SolutionOutlineSectionRow.__table__
        requirements = SolutionOutlineRequirementRefRow.__table__
        self.assertEqual([table.name for table in (version, sections, requirements)],
                         ["sol_outline_versions", "sol_outline_sections",
                          "sol_outline_requirement_refs"])
        self.assertTrue(all(table.schema == "plm" for table in (version, sections, requirements)))
        names = {constraint.name for table in (version, sections, requirements, SolutionSectionRow.__table__)
                 for constraint in table.constraints}
        self.assertTrue({"uq_sol_sections__id_outline_project",
                         "uq_sol_outline_versions__outline_no",
                         "fk_sol_outline_versions__supersedes",
                         "fk_sol_outline_sections__section",
                         "fk_sol_outline_requirements__requirement",
                         "uq_sol_outline_sections__version_ordinal",
                         "uq_sol_outline_requirements__version_requirement"} <= names)

    def test_migration_is_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261008_0137_solution_outline_version_foundation")
        self.assertEqual(migration.down_revision, "20261008_0136")
        self.assertIn("SolutionOutlineVersion Owner is not installed", migration._GUARDS)
        self.assertIn("SolutionOutlineVersion history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline SolutionOutlineVersion downgrade"):
                migration.downgrade()
        self.assertIn("SolutionOutlineVersion history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
