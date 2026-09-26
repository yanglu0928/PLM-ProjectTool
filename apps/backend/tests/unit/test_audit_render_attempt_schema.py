from importlib import import_module
from unittest import TestCase
from unittest.mock import patch
from plm_assistant.modules.audit.infrastructure.export_orm import render_attempts


class AuditRenderAttemptSchemaTests(TestCase):
    def test_orm_shape_matches_migration(self):
        migration=import_module("plm_assistant.migrations.versions.20260926_0041_audit_render_attempts")
        constraints={c.name:str(c.sqltext) for c in render_attempts.constraints if hasattr(c,"sqltext")}
        self.assertEqual(constraints["ck_aud_render_attempts__shape"],migration.SHAPE)

    def test_offline_downgrade_has_no_ddl(self):
        migration=import_module("plm_assistant.migrations.versions.20260926_0041_audit_render_attempts")
        with patch.object(migration.context,"is_offline_mode",return_value=True),patch.object(migration.op,"execute") as execute:
            with self.assertRaisesRegex(RuntimeError,"offline Audit rendering"):migration.downgrade()
            execute.assert_not_called()
