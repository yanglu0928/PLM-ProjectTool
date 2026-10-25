from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanWbsItemRow


class PlanWbsItemSchemaTests(unittest.TestCase):
    def test_version_parent_and_local_constraints(self) -> None:
        table = PlanWbsItemRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_wbs_items"))
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"uq_pln_wbs_items__id_version_plan_project",
                         "uq_pln_wbs_items__version_code",
                         "uq_pln_wbs_items__parent_ordinal",
                         "fk_pln_wbs_items__version", "fk_pln_wbs_items__parent",
                         "ck_pln_wbs_items__level_root", "ck_pln_wbs_items__not_self"} <= names)
        unique = next(constraint for constraint in table.constraints
                      if constraint.name == "uq_pln_wbs_items__parent_ordinal")
        self.assertTrue(unique.dialect_options["postgresql"]["nulls_not_distinct"])

    def test_migration_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0171_wbs_item_identity_foundation")
        self.assertEqual(migration.down_revision, "20261019_0170")
        self.assertIn("WbsItem Owner is not installed", migration._GUARDS)
        self.assertIn("WbsItem history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline WbsItem downgrade"):
                migration.downgrade()
        self.assertIn("WbsItem history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
