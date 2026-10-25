import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4, UUID
from importlib import import_module
from plm_assistant.modules.audit.application.retry_generation import AuditExportRetryGeneration
from plm_assistant.modules.audit.infrastructure.export_orm import retry_generations

class RetryGenerationTests(unittest.TestCase):
    def test_first_generation_shape_is_not_current_job_status(self):
        value=AuditExportRetryGeneration(*(uuid4() for _ in range(7)),3,0,datetime.now(timezone.utc))
        value.__post_init__()
        for changes in ({'new_export_id':value.source_export_id},{'new_job_id':value.source_job_id},
            {'source_failure_event_id':UUID(int=0)},{'expected_source_version':True},
            {'expected_source_version':-1},{'expected_source_version':9223372036854775808},
            {'first_job_version':1},{'first_job_version':False},{'created_at':datetime.now()}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(value,**changes)

    def test_private_orm_and_migration_chain(self):
        self.assertEqual(set(retry_generations.c.keys()),{'new_export_id','source_export_id','source_job_id',
            'source_failure_event_id','new_job_id','new_event_id','retry_audit_event_id',
            'expected_source_version','first_job_version','created_at'})
        self.assertEqual([c.name for c in retry_generations.primary_key.columns],['new_export_id'])
        self.assertTrue(all(not c.nullable for c in retry_generations.c))
        self.assertEqual(str(retry_generations.c.expected_source_version.type),'BIGINT')
        self.assertEqual(len(retry_generations.foreign_key_constraints),4)
        module=import_module('plm_assistant.migrations.versions.20260927_0045_audit_retry_generation')
        self.assertEqual(module.down_revision,'20260927_0044')
