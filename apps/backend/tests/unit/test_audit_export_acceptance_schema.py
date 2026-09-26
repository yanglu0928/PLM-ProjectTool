import importlib
import unittest
from unittest.mock import Mock,patch
from sqlalchemy import UniqueConstraint
from plm_assistant.modules.audit.infrastructure.export_orm import acceptances,AuditExportAcceptanceRow


class AcceptanceSchemaTests(unittest.TestCase):
    def test_immutable_result_mapping_minimal_refs(self):
        self.assertIs(AuditExportAcceptanceRow.__table__,acceptances)
        self.assertEqual(set(acceptances.c.keys()),{"export_id","job_id","event_id","request_audit_event_id","accepted_at"})
        self.assertEqual(set(acceptances.primary_key.columns.keys()),{"export_id"})
        self.assertEqual({tuple(c.columns.keys()) for c in acceptances.constraints if isinstance(c,UniqueConstraint)},
            {("job_id",),("event_id",),("request_audit_event_id",)})
        self.assertEqual({f.target_fullname for f in acceptances.foreign_keys},{"plm.aud_exports.export_id","plm.aud_events.audit_event_id"})

    def test_offline_down_no_ddl(self):
        migration=importlib.import_module("plm_assistant.migrations.versions.20260926_0038_audit_export_acceptance")
        self.assertEqual(migration.down_revision,"20260926_0037")
        with patch.object(migration.context,"is_offline_mode",return_value=True),patch.object(migration.op,"execute") as execute:
            with self.assertRaises(RuntimeError):migration.downgrade()
            execute.assert_not_called()

    def test_history_down_locks_then_refuses_without_drop(self):
        migration=importlib.import_module("plm_assistant.migrations.versions.20260926_0038_audit_export_acceptance")
        connection=Mock();connection.scalar.return_value=True
        with patch.object(migration.context,"is_offline_mode",return_value=False),patch.object(migration.op,"get_bind",return_value=connection),patch.object(migration.op,"execute") as execute,patch.object(migration.op,"drop_table") as drop:
            with self.assertRaises(RuntimeError):migration.downgrade()
            execute.assert_called_once_with("LOCK TABLE plm.aud_export_acceptances IN ACCESS EXCLUSIVE MODE")
            drop.assert_not_called()
