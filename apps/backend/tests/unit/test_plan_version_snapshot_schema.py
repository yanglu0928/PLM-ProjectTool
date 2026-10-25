from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import (
    PlanVersionExclusionRow,
    PlanVersionRow,
    PlanWbsConditionRow,
    PlanWbsItemRow,
    PlanWbsPrototypeRefRow,
    PlanWbsSupportRoleRow,
)


class PlanVersionSnapshotSchemaTests(unittest.TestCase):
    def test_calendar_and_explicit_exclusions_are_owned_by_version(self) -> None:
        version = PlanVersionRow.__table__
        exclusion = PlanVersionExclusionRow.__table__
        self.assertIn("calendar_ref", version.c)
        names = {item.name for item in exclusion.constraints}
        self.assertTrue({
            "fk_pln_version_exclusions__version",
            "fk_pln_version_exclusions__requirement",
            "fk_pln_version_exclusions__outline",
            "fk_pln_version_exclusions__section",
            "fk_pln_version_exclusions__spec",
            "ck_pln_version_exclusions__typed_target",
            "ck_pln_version_exclusions__kind",
        } <= names)

    def test_wbs_has_project_member_and_bounded_ordered_owned_values(self) -> None:
        item = PlanWbsItemRow.__table__
        self.assertTrue({
            "category_code", "owner_project_member_id", "planned_start_date",
            "planned_finish_date", "planned_duration_minutes", "actual_start_date",
            "actual_finish_date", "risk_summary", "explicit_exclusion_reason",
        } <= set(item.c.keys()))
        member_fk = next(fk for fk in item.foreign_key_constraints
                         if fk.name == "fk_pln_wbs_items__owner_member")
        self.assertEqual(tuple(col.name for col in member_fk.columns),
                         ("owner_project_member_id", "project_id"))
        roles = PlanWbsSupportRoleRow.__table__
        conditions = PlanWbsConditionRow.__table__
        self.assertIn("ck_pln_wbs_support_roles__role",
                      {c.name for c in roles.constraints})
        role_check = next(c for c in roles.constraints
                          if c.name == "ck_pln_wbs_support_roles__role")
        self.assertIn("support_role ~", str(role_check.sqltext))
        self.assertNotIn("PROJECT_MANAGER", str(role_check.sqltext))
        self.assertIn("uq_pln_wbs_conditions__item_kind_ordinal",
                      {c.name for c in conditions.constraints})

    def test_migration_is_additive_closed_and_refuses_history_loss(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0186_plan_version_snapshot_fields")
        self.assertEqual(migration.down_revision, "20261024_0185")
        self.assertEqual(migration._TABLES, (
            "pln_version_exclusions", "pln_wbs_support_roles", "pln_wbs_conditions",
        ))
        self.assertIn("Plan snapshot Owner is not installed", migration._GUARDS)
        self.assertIn("Plan snapshot history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline PlanVersion snapshot downgrade"):
                migration.downgrade()
        self.assertIn("PlanVersion snapshot history prevents downgrade",
                      inspect.getsource(migration.downgrade))
        self.assertIn("calendar_ref IS NOT NULL", inspect.getsource(migration._has_snapshot_history))

    def test_prototype_refs_use_composite_project_and_version_identity(self) -> None:
        table = PlanWbsPrototypeRefRow.__table__
        foreign_keys = {fk.name: tuple(element.target_fullname for element in fk.elements)
                        for fk in table.foreign_key_constraints}
        self.assertEqual(foreign_keys["fk_pln_item_prototypes__prototype_version"], (
            "plm.prt_prototype_versions.prototype_version_id",
            "plm.prt_prototype_versions.prototype_id",
            "plm.prt_prototype_versions.project_id",
        ))
        self.assertIn("uq_pln_item_prototypes__item_version",
                      {constraint.name for constraint in table.constraints})
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0187_plan_wbs_prototype_refs")
        self.assertEqual(migration.down_revision, "20261026_0186")
        self.assertIn("Plan WBS Prototype ref history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
