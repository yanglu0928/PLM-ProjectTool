"""Actual current Session/Root/pair and atomic cancel/Audit/immutable receipt."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel,AuditExportCancelRequestError
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources

spec=spec_from_file_location('_cancel_request_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    a=fixture.a;db=v['db']
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=SqlAlchemyAuditExportCancelSources(),audit=v['audit'])
    owner=AuditExportCancelRequestService(**deps)
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','plt_idempotency_receipts','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def command(accepted,scope):
        return RequestAuditExportCancel(accepted.intent.export_id,scope,accepted.intent.spec.project_id,v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),'Synthetic first cancellation')
    def reject(c,key,service=owner,code=None):
        before=snapshot()
        try:service.request(c,idempotency_key=key)
        except AuditExportCancelRequestError as exc:
            if code:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unsafe cancellation accepted')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,_=v['prepare'](scope,0);request=command(accepted,scope);key=str(fixture.uuid4())
        reject(replace(request,csrf_token=b'x'*32),key,code='AUTH_ACCESS_DENIED')
        v['guard'].enabled=False;reject(request,key,code='LICENSE_OPERATION_DENIED');v['guard'].enabled=True
        reject(replace(request,scope='DEPLOYMENT' if scope=='PROJECT' else 'PROJECT',project_id=None if scope=='PROJECT' else v['project']),key,code='RESOURCE_NOT_FOUND')
        class BrokenAudit:
            def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after actual Audit insert')
        reject(request,key,service=AuditExportCancelRequestService(**(deps|{'audit':BrokenAudit()})))
        class BrokenCancel:
            def read_facts(self,*args,**kwargs):return v['canceller'].read_facts(*args,**kwargs)
            def request_cancel(self,*args,**kwargs):v['canceller'].request_cancel(*args,**kwargs);raise RuntimeError('synthetic after actual Job writes')
        reject(request,key,service=AuditExportCancelRequestService(**(deps|{'cancellations':BrokenCancel()})))
        class EndDenied:
            count=0
            def require_in_transaction(self,*args,**kwargs):
                self.count+=1;proof=auth.require_in_transaction(*args,**kwargs)
                if self.count==2:raise fixture.a.AuditExportSubmitAuthorizationError('AUTH_ACCESS_DENIED')
                return proof
        reject(request,key,service=AuditExportCancelRequestService(**(deps|{'authorization':EndDenied()})))
        with ThreadPoolExecutor(max_workers=2) as pool:
            values=list(pool.map(lambda _:owner.request(request,idempotency_key=key),range(2)))
        assert values[0]==values[1];first=values[0];assert first.state=='CANCEL_REQUESTED' and first.changed is True
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AUDIT_EXPORT_CANCEL_REQUESTED' AND target_object_id=%s",(c.job_id,)).fetchone()==(1,)
        history=db.execute('SELECT cancel_requested_by,cancel_requested_at,cancel_reason FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()
        reject(replace(request,reason='Synthetic different payload'),key,code='CONFLICT_IDEMPOTENCY')
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        # Technical ack only to test immutable response drift; NOT Worker cancellation Owner.
        with v['uow']() as tx:v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref);tx.commit()
        before=snapshot();assert owner.request(replace(request,trace_id=fixture.uuid4()),idempotency_key=key)==first;assert snapshot()==before
        checked=owner.request(replace(request,reason='Synthetic later check'),idempotency_key=str(fixture.uuid4()))
        assert checked.state=='CANCELLED' and checked.changed is False
        assert db.execute('SELECT cancel_requested_by,cancel_requested_at,cancel_reason FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==history
        # PENDING is created through actual submit, not direct Job manipulation.
        now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        pending=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),spec),idempotency_key=str(fixture.uuid4()))
        immediate=owner.request(command(pending,scope),idempotency_key=str(fixture.uuid4()));assert immediate.state=='CANCELLED' and immediate.changed is True
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged)
        result_before=snapshot()['aud_export_results'];terminal=owner.request(command(accepted,scope),idempotency_key=str(fixture.uuid4()))
        assert terminal.state=='SUCCEEDED' and terminal.changed is False and snapshot()['aud_export_results']==result_before
        # Existing naked technical cancellation cannot be adopted as authorized first source.
        accepted,c,_=v['prepare'](scope,0)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic unaudited technical request');tx.commit()
        reject(command(accepted,scope),str(fixture.uuid4()))
    print('P04-P04-P02 PASS: actual dualScope authorized Root/pair cancellation+USER Audit+receipt, concurrent same key one first source, payload conflict, immutable CANCEL_REQUESTED replay after actual CANCELLED no writes, new-key check preserves first history, actual PENDING immediate/committed success unchanged; Audit/Job writes then faults and postauth deny rollback; naked technical cancellation refuses. No Worker ack/recovery Owner/HTTP/production completion.')


if __name__=='__main__':fixture.main(exercise=exercise)
