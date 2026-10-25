import importlib
import unittest
from unittest.mock import Mock,patch

module=importlib.import_module("plm_assistant.migrations.versions.20260926_0036_job_deployment_scope")


class JobScopeMigrationTests(unittest.TestCase):
    def test_upgrade_keeps_names_and_extends_only_scope(self):
        with patch.object(module,"op") as operations:
            module.upgrade()
            self.assertEqual(operations.drop_constraint.call_count,2)
            for call in operations.create_check_constraint.call_args_list:
                self.assertIn("'GLOBAL','DEPLOYMENT'",call.args[2])
                self.assertIn("scope='PROJECT' AND project_id IS NOT NULL",call.args[2])

    def test_down_locks_before_history_check_and_never_removes_history(self):
        order=[];bind=Mock();bind.scalar.side_effect=lambda query:(order.append("check") or True)
        with patch.object(module,"op") as operations,patch.object(module.context,"is_offline_mode",return_value=False):
            operations.execute.side_effect=lambda query:order.append("lock")
            operations.get_bind.return_value=bind
            with self.assertRaisesRegex(RuntimeError,"history exists; downgrade refused"):module.downgrade()
            self.assertEqual(order,["lock","check"])
            operations.drop_constraint.assert_not_called()

    def test_offline_down_refused_without_ddl(self):
        with patch.object(module,"op") as operations,patch.object(module.context,"is_offline_mode",return_value=True):
            with self.assertRaisesRegex(RuntimeError,"offline Job scope downgrade disabled"):module.downgrade()
            operations.execute.assert_not_called();operations.drop_constraint.assert_not_called()
