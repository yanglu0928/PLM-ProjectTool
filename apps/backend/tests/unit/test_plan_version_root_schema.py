from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanRow, PlanVersionRow


class PlanVersionRootSchemaTests(unittest.TestCase):
    def test_project_scoped_version_and_approved_pointer_reference(self) -> None:
        version = PlanVersionRow.__table__
        root = PlanRow.__table__
        self.assertEqual((version.schema, version.name), ("plm", "pln_plan_versions"))
        names = {constraint.name for constraint in version.constraints}
        self.assertTrue({"uq_pln_plan_versions__id_plan_project",
                         "uq_pln_plan_versions__plan_no",
                         "fk_pln_plan_versions__plan",
                         "fk_pln_plan_versions__supersedes",
                         "ck_pln_plan_versions__state",
                         "ck_pln_plan_versions__review_pair"} <= names)
        self.assertIn("fk_pln_plans__approved_version",
                      {constraint.name for constraint in root.constraints})
        self.assertNotIn("ck_pln_plans__approved_pointer_closed",
                         {constraint.name for constraint in root.constraints})

    def test_migration_is_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0170_plan_version_identity_foundation")
        self.assertEqual(migration.down_revision, "20261019_0169")
        self.assertIn("PlanVersion Owner is not installed", migration._GUARDS)
        self.assertIn("PlanVersion history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline PlanVersion downgrade"):
                migration.downgrade()
        self.assertIn("PlanVersion history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
