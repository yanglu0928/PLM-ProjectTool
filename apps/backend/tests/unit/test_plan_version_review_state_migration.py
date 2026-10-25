from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.plan.infrastructure.orm import PlanVersionReviewStateResultRow


class PlanVersionReviewStateMigrationTests(unittest.TestCase):
    def test_orm_exposes_closed_append_only_transition_result(self) -> None:
        table = PlanVersionReviewStateResultRow.__table__
        self.assertEqual("plm.pln_plan_version_review_state_results", table.fullname)
        self.assertEqual("review_state_result_id", next(iter(table.primary_key.columns)).name)
        self.assertTrue({
            "plan_version_id", "plan_id", "project_id", "review_id",
            "review_round_id", "event_type", "previous_state", "current_state",
            "actor_id", "created_at",
        }.issubset(table.c.keys()))
        self.assertTrue(any("pln_plan_versions.plan_version_id" in str(fk.target_fullname)
                            for fk in table.foreign_keys))

    def test_migration_extends_0189_and_closes_every_lifecycle_transition(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0190_plan_version_review_state_guard")
        self.assertEqual(migration.revision, "20261026_0190")
        self.assertEqual(migration.down_revision, "20261026_0189")
        upgrade = inspect.getsource(migration.upgrade) + migration._GUARDS
        for required in (
            "to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref']",
            "PlanVersion update is outside Review Owner",
            "subject_type<>'PLN-02'", "scope<>'PROJECT'",
            "rvw_round_events", "DEFERRABLE INITIALLY DEFERRED",
            "BEFORE INSERT OR UPDATE OR DELETE", "BEFORE TRUNCATE",
            "event_type='SUPERSEDED'",
        ):
            self.assertIn(required, upgrade)
        downgrade = inspect.getsource(migration.downgrade)
        self.assertIn("history prevents downgrade", downgrade)
        self.assertIn("version_state<>'DRAFT'", downgrade)

    def test_downgrade_stops_before_dropping_objects_when_history_exists(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0190_plan_version_review_state_guard")
        with patch.object(migration.context, "is_offline_mode", return_value=False), \
                patch.object(migration.op, "execute") as execute, \
                patch.object(migration.op, "get_bind") as get_bind:
            get_bind.return_value.execute.return_value.scalar_one.return_value = True
            with self.assertRaisesRegex(RuntimeError, "history prevents downgrade"):
                migration.downgrade()
            self.assertEqual(execute.call_count, 1)  # only acquire the protective lock


if __name__ == "__main__":
    unittest.main()
