"""Actual isolated PG cancellation versions, durable replay and rollback.

Positive License guard remains explicit synthetic; no HTTP/production proof.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel,AuditExportCancelRequestError
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor

spec=spec_from_file_location('_cancel_version_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    a=fixture.a;db=v['db'];sources=SqlAlchemyAuditExportCancelSources()
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=sources,audit=v['audit'])
    owner=AuditExportCancelRequestService(**deps)
    ack=AuditExportWorkerCancel(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=sources,audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','plt_idempotency_receipts','aud_export_results','doc_file_objects','aud_exports','aud_export_acceptances')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def version(accepted):return db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()[0]
    def target(accepted):return fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    def request(accepted,scope,expected):
        return RequestAuditExportCancel(accepted.intent.export_id,scope,accepted.intent.spec.project_id,v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),'Synthetic versioned cancellation',expected)
    def reject(c,key,code,service=owner):
        before=snapshot()
        try:service.request(c,idempotency_key=key)
        except AuditExportCancelRequestError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unsafe cancellation accepted')
        assert snapshot()==before
    def pending(scope):
        now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
    class ObserveCancel:
        versions=[]
        def read_facts(self,*args,**kwargs):
            result=v['canceller'].read_facts(*args,**kwargs);self.versions.append(result.lock_version);return result
        def request_cancel(self,*args,**kwargs):return v['canceller'].request_cancel(*args,**kwargs)
    class BrokenAudit:
        def append(self,*args,**kwargs):
            v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after actual Audit insert')
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted=pending(scope);c=request(accepted,scope,0);key=str(uuid4())
        assert version(accepted)==0
        reject(replace(c,expected_version=1),key,'VERSION_CONFLICT')
        reject(replace(c,csrf_token=b'x'*32),key,'AUTH_ACCESS_DENIED')
        v['guard'].enabled=False
        try:reject(c,key,'LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
        reject(c,key,'AUDIT_UNAVAILABLE',AuditExportCancelRequestService(**(deps|{'audit':BrokenAudit()})))
        assert version(accepted)==0
        observed=ObserveCancel();observed.versions=[]
        first=AuditExportCancelRequestService(**(deps|{'cancellations':observed})).request(c,idempotency_key=key)
        assert first.state=='CANCELLED' and first.changed and version(accepted)==2
        assert observed.versions==[0,2],observed.versions
        before=snapshot();assert owner.request(replace(c,trace_id=uuid4()),idempotency_key=key)==first;assert snapshot()==before
        reject(replace(c,expected_version=2),key,'CONFLICT_IDEMPOTENCY')
        reject(replace(c,expected_version=None),key,'CONFLICT_IDEMPOTENCY')
        reject(c,str(uuid4()),'VERSION_CONFLICT')
        checked=owner.request(replace(c,expected_version=2),idempotency_key=str(uuid4()))
        assert checked.state=='CANCELLED' and not checked.changed and version(accepted)==2
        # Existing internal unversioned receipts remain byte-for-byte fingerprint compatible.
        legacy=pending(scope);old=request(legacy,scope,None);oldkey=str(uuid4())
        oldfirst=owner.request(old,idempotency_key=oldkey)
        before=snapshot();assert owner.request(old,idempotency_key=oldkey)==oldfirst;assert snapshot()==before
        reject(replace(old,expected_version=0),oldkey,'CONFLICT_IDEMPOTENCY')
        running,command,_=v['prepare'](scope,0)
        assert version(running)==1
        c=request(running,scope,1);key=str(uuid4())
        reject(replace(c,expected_version=0),key,'VERSION_CONFLICT')
        with ThreadPoolExecutor(max_workers=2) as pool:
            values=list(pool.map(lambda _:owner.request(c,idempotency_key=key),range(2)))
        assert values[0]==values[1] and values[0].state=='CANCEL_REQUESTED' and values[0].changed
        assert version(running)==2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AUDIT_EXPORT_CANCEL_REQUESTED' AND target_object_id=%s",(running.job_id,)).fetchone()==(1,)
        before=snapshot();assert owner.request(c,idempotency_key=key)==values[0];assert snapshot()==before
        assert ack.acknowledge(command).state=='CANCELLED' and version(running)==3
        before=snapshot();assert owner.request(c,idempotency_key=key)==values[0];assert snapshot()==before
        v['guard'].enabled=False
        try:reject(c,key,'LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
        reject(c,str(uuid4()),'VERSION_CONFLICT')
        with v['uow']() as tx:assert v['canceller'].read_facts(tx,target=target(running)).lock_version==3
        # Distinct commands competing with the same version cannot both write.
        raced,command,_=v['prepare'](scope,0);c=request(raced,scope,1)
        def compete(_):
            try:return owner.request(c,idempotency_key=str(uuid4()))
            except AuditExportCancelRequestError as exc:return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(compete,range(2)))
        assert values.count('VERSION_CONFLICT')==1
        assert sum(getattr(value,'changed',False) is True for value in values)==1
        assert version(raced)==2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AUDIT_EXPORT_CANCEL_REQUESTED' AND target_object_id=%s",(raced.job_id,)).fetchone()==(1,)
        assert ack.acknowledge(command).state=='CANCELLED' and version(raced)==3
        succeeded,command,staged=v['prepare'](scope,0);v['worker'].publish(command,staged)
        assert version(succeeded)==2
        c=request(succeeded,scope,1);key=str(uuid4())
        reject(c,key,'VERSION_CONFLICT')
        before=snapshot()['aud_export_results']
        checked=owner.request(replace(c,expected_version=2),idempotency_key=key)
        assert checked.state=='SUCCEEDED' and not checked.changed and version(succeeded)==2
        assert snapshot()['aud_export_results']==before
    print('JOB-02-A01 PASS: actual dualScope locked v0 immediate cancel v2 (same-UOW refreshed), running v1->request v2->actual controlled Worker ack v3; concurrent same-key one first Audit/receipt, stale-original replay unchanged, changed version/legacy fingerprint conflicts and stale new key no writes; current CSRF/License and actual Audit-write fault full rollback. No HTTP/formal trust/production/Gate/package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
