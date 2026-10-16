from importlib import import_module
from unittest import TestCase
from dataclasses import replace
from uuid import uuid4
from plm_assistant.modules.audit.infrastructure.export_orm import cancel_versions
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelReceipt,AuditExportCancelRequestError

class CancelVersionSchemaTests(TestCase):
    def test_owned_minimal_schema_and_migration_parent(self):
        self.assertEqual(set(cancel_versions.c.keys()),{'audit_event_id','lock_version'})
        self.assertEqual([c.name for c in cancel_versions.primary_key.columns],['audit_event_id'])
        self.assertEqual(str(cancel_versions.c.lock_version.type),'BIGINT')
        self.assertFalse(cancel_versions.c.lock_version.nullable)
        m=import_module('plm_assistant.migrations.versions.20260927_0044_audit_cancel_version_snapshot')
        self.assertEqual(m.down_revision,'20260927_0043')
    def test_receipt_version_is_strict_optional_for_old_history(self):
        original=AuditExportCancelReceipt(uuid4(),'CANCELLED',True,uuid4())
        self.assertIsNone(original.lock_version)
        for version in (True,-1,2**63,0.0,'2'):
            with self.assertRaises(AuditExportCancelRequestError):replace(original,lock_version=version)
        for version in (0,2**63-1):self.assertEqual(replace(original,lock_version=version).lock_version,version)
