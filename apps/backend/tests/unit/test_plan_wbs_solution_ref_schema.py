from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanWbsSolutionRefRow


class PlanWbsSolutionRefSchemaTests(unittest.TestCase):
    def test_three_typed_fixed_source_constraints(self) -> None:
        table = PlanWbsSolutionRefRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_item_solution_refs"))
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"fk_pln_item_solutions__wbs",
                         "fk_pln_item_solutions__outline",
                         "fk_pln_item_solutions__section",
                         "fk_pln_item_solutions__spec",
                         "uq_pln_item_solutions__item_ordinal",
                         "ck_pln_item_solutions__ordinal",
                         "ck_pln_item_solutions__typed_target"} <= names)
        indexes = {index.name: index for index in table.indexes}
        for kind in ("outline", "section", "spec"):
            self.assertTrue(indexes[f"uq_pln_item_solutions__{kind}"].unique)

    def test_migration_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0175_wbs_solution_ref_foundation")
        self.assertEqual(migration.down_revision, "20261019_0174")
        self.assertIn("WbsSolutionRef Owner is not installed", migration._GUARDS)
        self.assertIn("WbsSolutionRef history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline WbsSolutionRef downgrade"):
                migration.downgrade()
        self.assertIn("WbsSolutionRef history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
