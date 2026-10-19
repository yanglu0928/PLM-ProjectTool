from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanMilestoneItemRefRow, PlanMilestoneRow


class PlanMilestoneSchemaTests(unittest.TestCase):
    def test_version_scope_and_wbs_links(self) -> None:
        milestone = PlanMilestoneRow.__table__
        links = PlanMilestoneItemRefRow.__table__
        self.assertEqual((milestone.schema, milestone.name), ("plm", "pln_milestones"))
        self.assertEqual((links.schema, links.name), ("plm", "pln_milestone_item_refs"))
        names = {constraint.name for table in (milestone, links)
                 for constraint in table.constraints}
        self.assertTrue({"uq_pln_milestones__id_version_plan_project",
                         "fk_pln_milestones__version", "ck_pln_milestones__duration",
                         "ck_pln_milestones__acceptance", "fk_pln_milestone_items__milestone",
                         "fk_pln_milestone_items__wbs",
                         "uq_pln_milestone_items__milestone_item",
                         "uq_pln_milestone_items__milestone_ordinal"} <= names)

    def test_migration_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0173_milestone_foundation")
        self.assertEqual(migration.down_revision, "20261019_0172")
        self.assertEqual(migration._TABLES,
                         ("pln_milestones", "pln_milestone_item_refs"))
        self.assertIn("PlanMilestone Owner is not installed", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline PlanMilestone downgrade"):
                migration.downgrade()
        self.assertIn("PlanMilestone history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
