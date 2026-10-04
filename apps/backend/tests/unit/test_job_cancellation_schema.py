import importlib
import unittest
from unittest.mock import Mock,patch
from plm_assistant.modules.jobs.infrastructure.orm import JobRow


class CancellationSchemaTests(unittest.TestCase):
    def test_nullable_group_and_user_fk(self):
        table=JobRow.__table__
        for field in ("cancel_requested_by","cancel_reason","cancel_requested_at"):
            self.assertTrue(table.c[field].nullable)
        self.assertEqual({fk.target_fullname for fk in table.c.cancel_requested_by.foreign_keys},{"plm.auth_users.user_id"})
        shape=next(str(c.sqltext) for c in table.constraints if c.name=="ck_job_jobs__cancel_shape")
        self.assertIn("isfinite(cancel_requested_at)",shape)
        self.assertIn("CANCEL_REQUESTED",shape)

    def test_offline_down_does_not_ddl(self):
        migration=importlib.import_module("plm_assistant.migrations.versions.20260926_0039_job_cancellation_history")
        self.assertEqual(migration.down_revision,"20260926_0038")
        with patch.object(migration.context,"is_offline_mode",return_value=True),patch.object(migration.op,"execute") as execute:
            with self.assertRaises(RuntimeError):migration.downgrade()
            execute.assert_not_called()

    def test_history_down_locks_before_refusing(self):
        migration=importlib.import_module("plm_assistant.migrations.versions.20260926_0039_job_cancellation_history")
        bind=Mock();bind.scalar.return_value=True
        with patch.object(migration.context,"is_offline_mode",return_value=False),patch.object(migration.op,"get_bind",return_value=bind),patch.object(migration.op,"execute") as execute,patch.object(migration.op,"drop_column") as drop:
            with self.assertRaises(RuntimeError):migration.downgrade()
            execute.assert_called_once_with("LOCK TABLE plm.job_jobs IN ACCESS EXCLUSIVE MODE")
            drop.assert_not_called()
