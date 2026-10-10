import unittest
from importlib import import_module
from unittest.mock import Mock,patch
from plm_assistant.modules.jobs.infrastructure.orm import JobRow

class JobResourceVersionSchemaTests(unittest.TestCase):
    def test_orm_matches_additive_version(self):
        column=JobRow.__table__.c.lock_version
        self.assertFalse(column.nullable)
        self.assertEqual(str(column.server_default.arg),'0')
        self.assertIn('ck_job_jobs__lock_version',{c.name for c in JobRow.__table__.constraints})
    def test_migration_parent_trigger_and_down_preserve_jobs(self):
        migration=import_module('plm_assistant.migrations.versions.20260927_0043_job_resource_version')
        self.assertEqual(migration.down_revision,'20260926_0042')
        operations=Mock()
        with patch.object(migration,'op',operations):
            migration.upgrade();migration.downgrade()
        ddl='\n'.join(str(c.args[0]) for c in operations.execute.call_args_list)
        self.assertIn('BEFORE UPDATE',ddl)
        self.assertIn("ARRAY['lock_version','lease_expires_at']",ddl)
        self.assertIn('OLD.lock_version+1',ddl)
        self.assertIn('9223372036854775807',ddl)
        self.assertIn('NEW.lock_version IS DISTINCT FROM OLD.lock_version',ddl)
        self.assertNotIn('DROP TABLE',ddl)
        operations.drop_column.assert_called_once_with('job_jobs','lock_version',schema='plm')
