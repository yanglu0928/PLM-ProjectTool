from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
from plm_assistant.entrypoints.audit_worker import AuditWorkerSettings,create_audit_export_worker
from plm_assistant.modules.platform.infrastructure.worker_database import WorkerDatabaseRuntime,WorkerDatabaseLimits


class WorkerCompositionTests(TestCase):
    def setUp(self):
        self.database=WorkerDatabaseRuntime(runtime=Mock(),limits=WorkerDatabaseLimits())
        self.database.is_ready=Mock(return_value=True)
        self.actor=Mock(spec=['assert_current']);self.actor.assert_current.return_value=uuid4()
        self.guard=Mock(spec=['require_valid']);self.projects=Mock(spec=['require_in_transaction'])
        self.storage=Mock(spec=['staging_sink','verify_staged','inspect','promote'])
        self.deps=dict(database=self.database,projects=self.projects,license_guard=self.guard,system_actor=self.actor,storage=self.storage,settings=AuditWorkerSettings('composition-unit'))

    def test_startup_current_schema_and_identity_fixed_no_business_permission(self):
        with patch('plm_assistant.entrypoints.audit_worker._schema_current',return_value=True):loop=create_audit_export_worker(**self.deps)
        step=loop._step
        self.assertIs(step._admission._actor,self.actor)
        self.assertIs(step._executor._reader._supervisor,step._admission._supervisor)
        self.assertIs(step._sweep._exhaustion._supervisor,step._admission._supervisor)
        self.guard.require_valid.assert_not_called();self.storage.promote.assert_not_called()
        loop.request_stop();self.assertEqual(loop.run().reason,'STOPPED')

    def test_database_or_schema_rejected_before_identity_and_no_side_effects(self):
        self.database.is_ready.return_value=False
        with self.assertRaises(RuntimeError):create_audit_export_worker(**self.deps)
        self.actor.assert_current.assert_not_called()
        self.database.is_ready.return_value=True
        with patch('plm_assistant.entrypoints.audit_worker._schema_current',return_value=False):
            with self.assertRaises(RuntimeError):create_audit_export_worker(**self.deps)
        self.actor.assert_current.assert_not_called()

    def test_missing_dependency_or_identity_unavailable_closed(self):
        with self.assertRaises(ValueError):create_audit_export_worker(**(self.deps|{'storage':None}))
        self.database.is_ready.assert_not_called()
        self.actor.assert_current.return_value=None
        with patch('plm_assistant.entrypoints.audit_worker._schema_current',return_value=True):
            with self.assertRaises(RuntimeError):create_audit_export_worker(**self.deps)

    def test_settings_reject_unsafe_timing_before_runtime(self):
        for kwargs in ({'heartbeat_seconds':21},{'poll_seconds':True},{'poll_seconds':float('nan')},{'stop_timeout_seconds':31}):
            with self.assertRaises(ValueError):AuditWorkerSettings('worker',**kwargs)
