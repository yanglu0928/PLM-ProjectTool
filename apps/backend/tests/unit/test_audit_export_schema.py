import importlib
import unittest
from unittest.mock import Mock, patch
from sqlalchemy import CheckConstraint
from plm_assistant.modules.audit.infrastructure.export_orm import exports, members, captures, AuditExportRow, AuditExportMemberRow, AuditExportCaptureRow


class AuditExportSchemaTests(unittest.TestCase):
    def test_safe_owned_fields_and_mappings(self):
        for table, row in ((exports,AuditExportRow),(members,AuditExportMemberRow),(captures,AuditExportCaptureRow)):
            self.assertIs(row.__table__,table)
            self.assertEqual(table.schema,"plm")
            self.assertFalse({"session","token","csrf","payload","body","path","secret"} & set(table.c.keys()))
        self.assertEqual(set(members.c.keys()),{"export_id","position","event_id","occurred_at","created_xid"})
        self.assertEqual(set(captures.primary_key.columns.keys()),{"export_id"})
        self.assertEqual(set(members.primary_key.columns.keys()),{"export_id","position"})

    def test_checks_and_owned_source_constraints(self):
        self.assertEqual(len([c for c in exports.constraints if isinstance(c,CheckConstraint)]),6)
        self.assertEqual({fk.target_fullname for fk in members.foreign_keys},{"plm.aud_exports.export_id","plm.aud_events.audit_event_id"})
        unique={tuple(c.columns.keys()) for c in members.constraints if c.__class__.__name__=="UniqueConstraint"}
        self.assertIn(("export_id","event_id"),unique)

    def test_offline_and_history_down_fail_before_drop(self):
        migration=importlib.import_module("plm_assistant.migrations.versions.20260926_0037_audit_export_capture")
        self.assertEqual(migration.down_revision,"20260926_0036")
        with patch.object(migration.context,"is_offline_mode",return_value=True),patch.object(migration.op,"execute") as execute:
            with self.assertRaises(RuntimeError):migration.downgrade()
            execute.assert_not_called()
        connection=Mock();connection.scalar.return_value=True
        with patch.object(migration.context,"is_offline_mode",return_value=False),patch.object(migration.op,"get_bind",return_value=connection),patch.object(migration.op,"execute") as execute,patch.object(migration.op,"drop_table") as drop:
            with self.assertRaises(RuntimeError):migration.downgrade()
            execute.assert_called_once_with("LOCK TABLE plm.aud_exports, plm.aud_export_members, plm.aud_export_captures IN ACCESS EXCLUSIVE MODE")
            drop.assert_not_called()
