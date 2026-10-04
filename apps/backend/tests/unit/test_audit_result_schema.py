from importlib import import_module
from unittest import TestCase
from unittest.mock import patch
from plm_assistant.modules.audit.infrastructure.export_orm import results


class AuditResultSchemaTests(TestCase):
    def test_orm_shape_matches_migration(self):
        migration=import_module('plm_assistant.migrations.versions.20260926_0042_audit_export_results')
        constraints={c.name:str(c.sqltext) for c in results.constraints if hasattr(c,'sqltext')}
        self.assertEqual(constraints['ck_aud_export_results__shape'],migration.SHAPE)
        self.assertEqual({f.target_fullname for f in results.foreign_keys},{
            'plm.aud_exports.export_id','plm.aud_export_render_attempts.render_attempt_id','plm.aud_events.audit_event_id'})

    def test_offline_downgrade_has_no_ddl(self):
        migration=import_module('plm_assistant.migrations.versions.20260926_0042_audit_export_results')
        with patch.object(migration.context,'is_offline_mode',return_value=True),patch.object(migration.op,'execute') as execute:
            with self.assertRaisesRegex(RuntimeError,'offline Audit result'):migration.downgrade()
            execute.assert_not_called()
