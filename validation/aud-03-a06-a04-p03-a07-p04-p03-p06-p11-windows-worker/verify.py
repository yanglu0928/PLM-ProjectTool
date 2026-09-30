"""Windows real temporary account DB credential + fixed root; License remains synthetic."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import secrets
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from psycopg import sql
from plm_assistant.entrypoints import worker_windows as cli
from plm_assistant.entrypoints.audit_worker_signals import run_audit_worker_process
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url,write_database_url,DatabaseCredentialError
from plm_assistant.modules.platform.infrastructure.maintenance_admission import MAINTENANCE_LOCK_KEY
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

spec=spec_from_file_location('_windows_worker_step_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p06-p07-worker-step'/'verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p)


def exercise(v):
    target='PLMProjectTool/Test/AuditWorker-'+uuid4().hex
    try:read_database_url(target=target)
    except DatabaseCredentialError:pass
    else:raise AssertionError('synthetic credential target already exists')
    lib=ctypes.WinDLL('Advapi32',use_last_error=True)
    lib.CredDeleteW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD];lib.CredDeleteW.restype=wintypes.BOOL
    url=v['url'].set(password=secrets.token_urlsafe(24));write_database_url(url.render_as_string(hide_password=False),target=target)
    settings=BootstrapSettings(data_root=v['file_root'],selected_mac='00-11-22-33-44-55')
    original_database=cli.create_worker_database_runtime;original_storage=cli.LocalAuditExportFileStorage
    created=[];loops=[];disposed=[]
    def database(secret,**kwargs):
        db=original_database(secret,**kwargs);created.append(db);original_uow=db.unit_of_work;original_dispose=db.dispose
        @contextmanager
        def counted():
            with original_uow() as tx:
                v['active'][0]+=1
                try:yield tx
                finally:v['active'][0]-=1
        db.unit_of_work=counted
        def dispose():disposed.append(db);original_dispose()
        db.dispose=dispose;return db
    def storage(inner):
        actual=original_storage(inner)
        class Guarded:
            def staging_sink(self,c):assert v['active'][0]==0;return actual.staging_sink(c)
            def verify_staged(self,c):assert v['active'][0]==0;return actual.verify_staged(c)
            def inspect(self,c):assert v['active'][0]==0;return actual.inspect(c)
            def promote(self,c,*,mode='new'):assert v['active'][0]==0;return actual.promote(c,mode=mode)
        return Guarded()
    def decorate(unused):
        db,loop=cli.create_windows_audit_worker(settings);loops.append((db,loop));step=loop._step;original=step.step;values=[]
        assert loop._maintenance_admission is db.maintenance_admission and db.maintenance_admission is not None
        def counted():
            assert v['db'].execute('SELECT pg_try_advisory_lock(%s)',(MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
            value=original();values.append(value);return value
        step.step=counted
        class Wrapped:
            def request_stop(self):loop.request_stop()
            def step(self):
                result=run_audit_worker_process(loop,max_steps=1);value=values.pop();assert not values
                assert result.reason==('STOPPED' if value.kind=='STOPPED' else 'LIMIT')
                return value
        return Wrapped()
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    try:
        with patch.object(cli,'read_database_url',side_effect=lambda:read_database_url(target=target)),patch.object(cli,'create_worker_database_runtime',side_effect=database):
            # Current installed public key genuinely absent: fixed trust startup MUST fail.
            from plm_assistant.modules.license.infrastructure.packaged_product_key import PackagedProductKey,PackagedProductKeyError
            try:PackagedProductKey()
            except PackagedProductKeyError:
                before=snapshot()
                try:cli.create_windows_audit_worker(settings)
                except RuntimeError:pass
                else:raise AssertionError('missing packaged trust accepted')
                assert snapshot()==before and created[-1] in disposed
            else:raise AssertionError('fixture expected unprovisioned packaged product key; re-evaluate formal state')
            with patch.object(cli,'create_windows_worker_license_services',return_value=SimpleNamespace(guard=v['guard'])),patch.object(cli,'create_windows_system_actor',return_value=v['system_actor']),patch.object(cli,'LocalAuditExportFileStorage',side_effect=storage):
                p.exercise(v,decorate_step=decorate)
            before=snapshot()
            v['db'].execute("UPDATE plm.plt_maintenance_state SET state='MAINTENANCE',lock_version=lock_version+1 WHERE state_id=1")
            try:
                for db,loop in loops:
                    try:loop.run(max_steps=1)
                    except AuditExportWorkerError:pass
                    else:raise AssertionError('Audit Worker ran in MAINTENANCE')
                assert snapshot()==before
            finally:
                v['db'].execute("UPDATE plm.plt_maintenance_state SET state='RUNNING',lock_version=lock_version+1 WHERE state_id=1")
            for db,loop in loops:
                with loop.quiescent():db.dispose()
    finally:
        for db in created:
            if db not in disposed:
                matched=[loop for owned,loop in loops if owned is db]
                if matched:
                    with matched[0].quiescent():db.dispose()
                else:db.dispose()  # Construction only: no business work/heartbeat started.
        assert lib.CredDeleteW(target,1,0)
    print('P06-P11 PASS: actual temporary Windows account DB credential mapped only in fixture, bounded PG18/current schema/fixed Windows root and real temporary Vault SystemActor; absent real packaged public key fails before job writes and disposes construction DB. Synthetic License replacement explicitly test-only: dualScope real queue/heartbeat/file publication/current User denial via process adapter, idle/stop readonly and quiescent closure. Formal key/default account credential/Console/SCM/Server2025/other platforms/package NOT proved; synthetic credential removed.')


if __name__=='__main__':p.fixture.main(exercise=exercise)
