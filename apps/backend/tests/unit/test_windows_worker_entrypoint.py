from contextlib import contextmanager,redirect_stderr,redirect_stdout
from io import StringIO
from pathlib import Path
from threading import Event
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
from . import test_audit_worker_loop as fixture
from plm_assistant.entrypoints import worker_windows as cli
from plm_assistant.entrypoints import windows_license_runtime as lic
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.worker_database import WorkerDatabaseRuntime,WorkerDatabaseLimits
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.worker_loop import AuditExportLoopResult


class WindowsWorkerTests(TestCase):
    def setUp(self):self.settings=BootstrapSettings(data_root=Path.cwd(),selected_mac='00-11-22-33-44-55')

    def test_missing_fixed_sources_never_reach_worker_or_expose_exception(self):
        db=Mock()
        with patch.object(cli,'read_database_url',return_value='synthetic-db-source') as read,patch.object(cli,'create_worker_database_runtime',return_value=db),patch.object(cli,'create_windows_worker_license_services',side_effect=RuntimeError('private value')),patch.object(cli,'create_audit_export_worker') as compose:
            with self.assertRaises(RuntimeError) as cm:cli.create_windows_audit_worker(self.settings)
        self.assertEqual(str(cm.exception),'Windows audit worker unavailable');db.dispose.assert_called_once();read.assert_called_once_with();compose.assert_not_called()

    def test_worker_license_same_fixed_trust_chain(self):
        db=WorkerDatabaseRuntime(runtime=Mock(),limits=WorkerDatabaseLimits());db.is_ready=Mock(return_value=True)
        product,machine,integrity=Mock(),Mock(),Mock()
        with patch('plm_assistant.entrypoints.audit_worker._schema_current',return_value=True),patch.object(lic,'PackagedProductKey',return_value=product) as key,patch.object(lic,'WindowsSelectedMachine',return_value=machine),patch.object(lic,'create_windows_trusted_time_integrity',return_value=integrity),patch.object(lic,'_assemble',return_value='synthetic-services') as assemble:
            self.assertEqual(lic.create_windows_worker_license_services(db,self.settings),'synthetic-services')
        key.assert_called_once_with();machine.selected_mac.assert_called_once();assemble.assert_called_once_with(db,product=product,machine=machine,integrity=integrity)

    def test_cli_static_invalid_and_missing_config(self):
        for args,expected in ((['worker'],2),(['worker','missing-bootstrap.yaml'],1),(['worker','anything','--database-url'],2)):
            output=StringIO()
            with patch.object(cli.sys,'argv',args),redirect_stderr(output),patch.object(cli,'create_windows_audit_worker') as compose:self.assertEqual(cli.main(),expected)
            compose.assert_not_called();self.assertNotIn('missing-bootstrap.yaml',output.getvalue())

    def test_once_limit_not_service_readiness_and_quiescent_dispose(self):
        loop=Mock();db=Mock()
        @contextmanager
        def quiet():yield
        loop.quiescent=quiet
        with patch.object(cli.sys,'argv',['worker','bootstrap','--once']),patch.object(cli.Path,'resolve',return_value=Path.cwd()),patch.object(cli,'load_bootstrap_settings',return_value=self.settings),patch.object(cli,'create_windows_audit_worker',return_value=(db,loop)),patch.object(cli,'register_runtime_process',return_value=quiet()),patch.object(cli,'run_audit_worker_process',return_value=AuditExportLoopResult('LIMIT',1,0,0,0,0,1)),redirect_stdout(StringIO()) as output:
            self.assertEqual(cli.main(),0)
        db.dispose.assert_called_once();self.assertIn('readiness not asserted',output.getvalue())
        self.assertIn('sources rejected: 1; no terminal state asserted',output.getvalue())

    def test_real_live_heartbeat_blocks_quiescent_closure(self):
        f=fixture.WorkerLoopTests();f.setUp();sup=f.t.t.supervisor
        entered,release=Event(),Event()
        def heartbeat(*args,**kwargs):entered.set();release.wait(3);return f.t.t.claim
        sup._heartbeats.heartbeat.side_effect=heartbeat
        handle=sup.start(f.t.t.command,lease_seconds=3,interval_seconds=.1)
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(AuditExportWorkerError):
                with f.loop.quiescent():pass
        finally:release.set();handle.stop()
        with f.loop.quiescent():
            with self.assertRaises(AuditExportWorkerError):f.loop.run(max_steps=1)
