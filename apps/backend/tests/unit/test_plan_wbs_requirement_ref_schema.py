from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanWbsRequirementRefRow


class PlanWbsRequirementRefSchemaTests(unittest.TestCase):
    def test_fixed_version_and_same_project_constraints(self) -> None:
        table = PlanWbsRequirementRefRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_item_requirement_refs"))
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"fk_pln_item_requirements__wbs",
                         "fk_pln_item_requirements__requirement",
                         "uq_pln_item_requirements__item_version",
                         "uq_pln_item_requirements__item_ordinal",
                         "ck_pln_item_requirements__ordinal"} <= names)

    def test_migration_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0174_wbs_requirement_ref_foundation")
        self.assertEqual(migration.down_revision, "20261019_0173")
        self.assertIn("WbsRequirementRef Owner is not installed", migration._GUARDS)
        self.assertIn("WbsRequirementRef history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline WbsRequirementRef downgrade"):
                migration.downgrade()
        self.assertIn("WbsRequirementRef history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
