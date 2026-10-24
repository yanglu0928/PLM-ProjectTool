"""Actual Windows CLI subprocesses with temporary Credential/Vault and PG."""
import ctypes
from ctypes import wintypes
from datetime import datetime,timedelta,timezone
import hashlib
from importlib.util import module_from_spec,spec_from_file_location
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url,write_database_url,DatabaseCredentialError

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    spec=spec_from_file_location(name,path);module=module_from_spec(spec);spec.loader.exec_module(module);return module
fixture=load('_child_publication',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
console=load('_child_console',ROOT/'validation/aud-p06-p12-external-console/verify.py')

CHILD=r'''
from contextlib import ExitStack,contextmanager
from pathlib import Path
from threading import Event,Thread,local
from types import SimpleNamespace
from time import monotonic
from unittest.mock import patch
import sys
from plm_assistant.entrypoints import worker_windows as cli
from plm_assistant.entrypoints.audit_worker_signals import audit_worker_signals
from plm_assistant.entrypoints.windows_system_actor import create_windows_system_actor
from plm_assistant.modules.platform.infrastructure.windows_system_actor import WORKER_SYSTEM_ACTOR_KEY_REF
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url
target,ref,mode,bootstrap=sys.argv[1:]
vault=WindowsSecretKeyProvider()
class Mapping:
    def resolve_key(self,key):
        assert key==WORKER_SYSTEM_ACTOR_KEY_REF
        return vault.resolve_key(ref)
class TestOnlyGuard:
    def require_valid(self,*,trace_id):return None
actor=create_windows_system_actor(resolver=Mapping());actor.assert_current()
release=Event();loop_holder=[];counts=local()
def control():
    for line in sys.stdin:
        if line.strip()=='RELEASE':release.set()
        if line.strip()=='STOP':
            if loop_holder:loop_holder[0].request_stop()
            release.set();return
Thread(target=control,daemon=True).start()
original_db=cli.create_worker_database_runtime
def database(secret):
    db=original_db(secret);original=db.unit_of_work
    @contextmanager
    def uow():
        with original() as tx:
            counts.n=getattr(counts,'n',0)+1
            try:yield tx
            finally:counts.n-=1
    db.unit_of_work=uow;return db
original_storage=cli.LocalAuditExportFileStorage
def storage(inner):
    actual=original_storage(inner)
    class Gate:
        first=True
        def staging_sink(self,c):
            assert getattr(counts,'n',0)==0
            if mode=='active' and self.first:
                self.first=False;print('ACTIVE',flush=True)
                deadline=monotonic()+30
                while not release.wait(.05):assert monotonic()<deadline
            return actual.staging_sink(c)
        def verify_staged(self,c):assert getattr(counts,'n',0)==0;return actual.verify_staged(c)
        def inspect(self,c):assert getattr(counts,'n',0)==0;return actual.inspect(c)
        def promote(self,c,*,mode='new'):assert getattr(counts,'n',0)==0;return actual.promote(c,mode=mode)
    return Gate()
def run(loop,*,max_steps=None):
    loop_holder.append(loop)
    with audit_worker_signals(loop) as probe:
        print('READY',flush=True)
        result=loop.run(max_steps=max_steps,stop_requested=probe)
    print('RESULT '+result.reason+' '+str(result.executed),flush=True)
    return result
with ExitStack() as stack:
    stack.enter_context(patch.object(cli,'read_database_url',side_effect=lambda:read_database_url(target=target)))
    stack.enter_context(patch.object(cli,'create_worker_database_runtime',side_effect=database))
    if mode!='missing':
        stack.enter_context(patch.object(cli,'create_windows_worker_license_services',return_value=SimpleNamespace(guard=TestOnlyGuard())))
    stack.enter_context(patch.object(cli,'create_windows_system_actor',return_value=actor))
    stack.enter_context(patch.object(cli,'LocalAuditExportFileStorage',side_effect=storage))
    stack.enter_context(patch.object(cli,'run_audit_worker_process',side_effect=run))
    sys.argv=['worker',bootstrap]+(['--once'] if mode in ('once','missing') else [])
    status=cli.main()
raise SystemExit(status)
'''

def exercise(v):
    target='PLMProjectTool/Test/Child-'+uuid4().hex
    try:read_database_url(target=target)
    except DatabaseCredentialError:pass
    else:raise AssertionError('temporary target collision')
    write_database_url(v['url'].set(password=secrets.token_urlsafe(24)).render_as_string(hide_password=False),target=target)
    children=[]
    env=dict(os.environ);env['PLM_DATA_ROOT']=str(v['file_root']);env['PYTHONIOENCODING']='utf-8'
    def spawn(mode):
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        child=subprocess.Popen([sys.executable,'-c',CHILD,target,v['ref'],mode,str(ROOT/'apps/backend/config/bootstrap.example.yaml')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        lines=queue.Queue()
        def read():
            for line in child.stdout:lines.put(line.strip())
        reader=threading.Thread(target=read);reader.start();children.append((child,reader));return child,lines
    def expect(lines,value):
        if lines.get(timeout=30)!=value:raise RuntimeError('Actual worker child state failed')
    def finished(child,lines,kind,count):
        expect(lines,'RESULT '+kind+' '+str(count))
        expect(lines,'One bounded audit worker step finished; service readiness not asserted.' if kind=='LIMIT' else 'Audit worker stopped after draining known work.')
        assert child.wait(timeout=30)==0
    def signal_stop(child):
        assert child.poll() is None
        sender=subprocess.run([sys.executable,'-c',console.SENDER,str(child.pid)],capture_output=True,text=True,timeout=10)
        assert sender.returncode==0
    def pending(scope):
        now=datetime.now(timezone.utc);a=fixture.a
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
    def published(accepted):
        assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('SUCCEEDED',)
        with v['runtime'].unit_of_work() as tx:result=v['results'].get(tx,export_id=accepted.intent.export_id)
        assert result is not None
        state,locator=v['db'].execute('SELECT file_state,storage_locator FROM plm.doc_file_objects WHERE file_object_id=%s',(result.file_id,)).fetchone()
        path=(v['file_root']/locator).resolve();assert path.is_relative_to(v['file_root']) and state=='AVAILABLE'
        data=path.read_bytes();assert hashlib.sha256(data).digest()==result.file_sha256 and len(data)==result.byte_count
        assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(accepted.job_id,)).fetchone()==(1,)
        assert v['db'].execute('SELECT state FROM plm.job_leases WHERE job_id=%s',(accepted.job_id,)).fetchall()==[('RELEASED',)]
        assert v['db'].execute('SELECT completed_at IS NOT NULL,error_code FROM plm.job_attempts WHERE job_id=%s',(accepted.job_id,)).fetchone()==(True,None)
        assert v['db'].execute("SELECT actor_type,actor_id FROM plm.aud_events WHERE audit_event_id=%s",(result.publish_audit_event_id,)).fetchone()==('SYSTEM',v['identity'])
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    try:
        from plm_assistant.modules.license.infrastructure.packaged_product_key import PackagedProductKey,PackagedProductKeyError
        try:PackagedProductKey()
        except PackagedProductKeyError:pass
        else:raise AssertionError('Formal public key state changed; re-evaluate negative test')
        before=snapshot();child,lines=spawn('missing')
        expect(lines,'Windows audit worker unavailable; configuration, credentials or lifecycle rejected.')
        assert child.wait(timeout=30)==1 and snapshot()==before
        for scope in ('PROJECT','DEPLOYMENT'):
            accepted=pending(scope);child,lines=spawn('once');expect(lines,'READY');finished(child,lines,'LIMIT',1);published(accepted)
        before=snapshot();child,lines=spawn('idle');expect(lines,'READY');signal_stop(child);finished(child,lines,'STOPPED',0);assert snapshot()==before
        first=pending('PROJECT');second=pending('PROJECT');child,lines=spawn('active');expect(lines,'READY');expect(lines,'ACTIVE')
        signal_stop(child);child.stdin.write('RELEASE\n');child.stdin.flush();finished(child,lines,'STOPPED',1);published(first)
        assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(second.job_id,)).fetchone()==('PENDING',)
        assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(second.job_id,)).fetchone()==(0,)
        child,lines=spawn('once');expect(lines,'READY');finished(child,lines,'LIMIT',1);published(second)
    finally:
        for child,reader in children:
            if child.poll() is None:
                child.stdin.write('STOP\n');child.stdin.flush();child.wait(timeout=35)
            reader.join(timeout=2);assert not reader.is_alive();child.stdin.close();child.stdout.close()
        lib=ctypes.WinDLL('Advapi32',use_last_error=True);lib.CredDeleteW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD];lib.CredDeleteW.restype=wintypes.BOOL
        assert lib.CredDeleteW(target,1,0)
    print('P12-B02 PASS: actual independent Windows CLI/PG/Vault child processes dualScope publication and file hashes, absent real public key fails readonly, external idle stop readonly and active drain leaves second pending/unclaimed then independent once publishes it. Explicit test-only License guard; no formal trust/SCM/full package proof.')

if __name__=='__main__':fixture.main(exercise=exercise)
