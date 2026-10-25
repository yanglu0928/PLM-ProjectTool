from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanRow


class PlanApprovedPointerMigrationTests(unittest.TestCase):
    def test_orm_retains_composite_pointer_fk_without_closed_null_check(self) -> None:
        table = PlanRow.__table__
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("fk_pln_plans__approved_version", names)
        self.assertNotIn("ck_pln_plans__approved_pointer_closed", names)
        self.assertTrue(table.c.current_approved_version_ref.nullable)

    def test_migration_replaces_only_pointer_guard_and_defers_consistency(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0200_plan_approved_pointer_guard")
        self.assertEqual(migration.revision, "20261026_0200")
        self.assertEqual(migration.down_revision, "20261026_0190")
        upgrade = inspect.getsource(migration.upgrade) + migration._GUARDS
        for required in (
            "IF TG_OP='INSERT' THEN",
            "NEW.plan_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL",
            "to_jsonb(NEW)-ARRAY['current_approved_version_ref','lock_version']",
            "NEW.lock_version <> OLD.lock_version + 1",
            "Plan Approved pointer target is not current",
            "approved_count > 1 OR approved_pointer IS DISTINCT FROM approved_version",
            "Plan Approved pointer has no matching 0190 result",
            "Previous Plan Approved pointer has no SUPERSEDED result",
            "trg_pln_plans__approved_pointer_closure",
            "trg_pln_plan_versions__approved_pointer_closure",
            "trg_pln_plan_review_results__approved_pointer_closure",
            "DEFERRABLE INITIALLY DEFERRED",
            "drop_constraint",
        ):
            self.assertIn(required, upgrade)
        self.assertIn("Plan Approved pointer history requires audited migration", upgrade)
        self.assertIn("Plan Approved pointer history prevents downgrade",
                      inspect.getsource(migration.downgrade))

    def test_downgrade_refuses_pointer_or_lifecycle_history_before_changes(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0200_plan_approved_pointer_guard")
        with patch.object(migration.context, "is_offline_mode", return_value=False), \
                patch.object(migration.op, "execute") as execute, \
                patch.object(migration.op, "get_bind") as get_bind:
            get_bind.return_value.execute.return_value.scalar_one.return_value = True
            with self.assertRaisesRegex(
                    RuntimeError, "Plan Approved pointer history prevents downgrade"):
                migration.downgrade()
            self.assertEqual(execute.call_count, 1)  # only the protective table lock


if __name__ == "__main__":
    unittest.main()
