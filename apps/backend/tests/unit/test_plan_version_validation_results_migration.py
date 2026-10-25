from __future__ import annotations

import importlib
import inspect
import unittest

from plm_assistant.modules.plan.infrastructure.orm import PlanVersionValidationResultRow


class PlanVersionValidationResultsMigrationTests(unittest.TestCase):
    def test_orm_exposes_closed_minimal_report_snapshot(self) -> None:
        table = PlanVersionValidationResultRow.__table__
        self.assertEqual("plm.pln_plan_version_validation_results", table.fullname)
        self.assertEqual("audit_event_id", next(iter(table.primary_key.columns)).name)
        self.assertTrue({
            "plan_version_id", "plan_id", "project_id", "snapshot_fingerprint",
            "valid", "blocking_issues", "warnings", "coverage_summary", "checked_at",
        }.issubset(table.c.keys()))
        self.assertFalse({"body", "request_body", "response_body", "api_key"}
                         & set(table.c.keys()))

    def test_migration_is_append_only_and_refuses_downgrade_with_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0189_plan_version_validation_results")
        self.assertEqual(migration.revision, "20261026_0189")
        self.assertEqual(migration.down_revision, "20261026_0188")
        upgrade = inspect.getsource(migration.upgrade)
        self.assertIn("jsonb_typeof(blocking_issues)='array'", upgrade)
        self.assertIn("target_object_id=NEW.plan_version_id", upgrade)
        self.assertIn("PlanVersion validation reports are immutable", upgrade)
        self.assertIn("cannot be truncated", upgrade)
        downgrade = inspect.getsource(migration.downgrade)
        self.assertIn("_has_history()", downgrade)
        self.assertIn("history prevents downgrade", downgrade)


if __name__ == "__main__":
    unittest.main()
