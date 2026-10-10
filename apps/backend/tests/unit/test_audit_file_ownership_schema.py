"""Internal metadata contracts, not authorization or physical file proof."""
from importlib import import_module
from unittest import TestCase
from unittest.mock import patch
from plm_assistant.modules.document.infrastructure.orm import FileObjectRow


class AuditFileOwnershipSchemaTests(TestCase):
    def test_orm_matches_migration_constraints(self):
        migration=import_module("plm_assistant.migrations.versions.20260926_0040_audit_file_ownership")
        constraints={c.name:str(c.sqltext) for c in FileObjectRow.__table__.constraints if hasattr(c,"sqltext")}
        self.assertEqual(constraints["ck_doc_file_objects__usage"],migration.USAGE)
        self.assertEqual(constraints["ck_doc_file_objects__scope_project"],migration.SCOPE)

    def test_old_rows_default_to_document_not_audit(self):
        self.assertEqual(str(FileObjectRow.__table__.c.usage_kind.server_default.arg),"'DOCUMENT'")
        self.assertTrue(FileObjectRow.__table__.c.owner_object_id.nullable)
        self.assertIsNone(FileObjectRow.__table__.c.owner_object_id.server_default)

    def test_offline_downgrade_refuses_without_ddl(self):
        migration=import_module("plm_assistant.migrations.versions.20260926_0040_audit_file_ownership")
        with patch.object(migration.context,"is_offline_mode",return_value=True), patch.object(migration.op,"execute") as execute:
            with self.assertRaisesRegex(RuntimeError,"offline Audit file ownership"):
                migration.downgrade()
            execute.assert_not_called()
