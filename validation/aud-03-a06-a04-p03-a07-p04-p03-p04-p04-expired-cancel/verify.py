"""Actual DB expiry safety recovery, not an OS process termination assertion."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

spec=spec_from_file_location('_cancel_expiry_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    a=fixture.a;db=v['db'];sources=SqlAlchemyAuditExportCancelSources()
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    requests=AuditExportCancelRequestService(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=sources,audit=v['audit'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=sources,audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    owner=AuditExportWorkerCancel(**deps)
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def request(accepted,scope):
        return requests.request(RequestAuditExportCancel(accepted.intent.export_id,scope,accepted.intent.spec.project_id,
            v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),'Synthetic authorized expiry request'),idempotency_key=str(fixture.uuid4()))
    def reject(c,service=owner,method='recover_expired',code=None):
        before=snapshot()
        try:getattr(service,method)(c)
        except AuditExportWorkerError as exc:
            if code:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unsafe expiry recovery')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,staged=v['prepare'](scope,0,seconds=2);request(accepted,scope)
        history=db.execute('SELECT cancel_requested_by,cancel_requested_at,cancel_reason FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()
        reject(c,code='LEASE_NOT_EXPIRED');time.sleep(2.05)
        reject(c,method='acknowledge',code='STALE_LEASE')
        for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+1),replace(c,export_id=fixture.uuid4())):reject(wrong)
        class BrokenAudit:
            def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after Audit insert')
        reject(c,AuditExportWorkerCancel(**(deps|{'audit':BrokenAudit()})))
        class BrokenRecovery:
            def read_facts(self,*args,**kwargs):return v['canceller'].read_facts(*args,**kwargs)
            def recover_current_expired_cancel(self,*args,**kwargs):v['canceller'].recover_current_expired_cancel(*args,**kwargs);raise RuntimeError('synthetic after actual recovery writes')
        reject(c,AuditExportWorkerCancel(**(deps|{'cancellations':BrokenRecovery()})))
        class LostIdentity:
            count=0
            def assert_current(self):
                self.count+=1
                if self.count==2:raise RuntimeError('synthetic source loss')
                return v['system_actor'].assert_current()
        reject(c,AuditExportWorkerCancel(**(deps|{'system_actor':LostIdentity()})))
        actor=accepted.intent.actor_id
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=False
        try:v['worker'].capture(c)
        except AuditExportWorkerError:pass
        else:raise AssertionError('revoked business continued')
        before=snapshot();assert owner.recover_expired(c).state=='CANCELLED'
        assert db.execute('SELECT state,lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('CANCELLED',None)
        assert db.execute('SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()==('EXPIRED',)
        assert db.execute('SELECT error_code,completed_at IS NOT NULL FROM plm.job_attempts WHERE job_id=%s AND fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()==('JOB_CANCELLED',True)
        event=db.execute("SELECT actor_type,actor_id,original_actor_id,trace_id,event_scope,target_project_id,reason_code,before_state,after_state FROM plm.aud_events WHERE action='AUDIT_EXPORT_CANCEL_RECOVERED' AND target_object_id=%s",(c.job_id,)).fetchall()
        assert event==[('SYSTEM',v['identity'],actor,accepted.intent.trace_id,scope,accepted.intent.spec.project_id,'LEASE_EXPIRED','CANCEL_REQUESTED','CANCELLED')]
        assert len(snapshot()['aud_events'])==len(before['aud_events'])+1
        for t in ('aud_export_results','doc_file_objects'):assert snapshot()[t]==before[t]
        assert db.execute('SELECT cancel_requested_by,cancel_requested_at,cancel_reason FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==history
        stage,_=fixture.f._locators(staged.content.coordinate);assert (v['file_root']/stage).is_file()
        reject(c,code='STALE_LEASE')
        v['guard'].enabled=True;db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);reject(c)
        accepted,c,_=v['prepare'](scope,0,seconds=2)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic unaudited request');tx.commit()
        time.sleep(2.05);reject(c)
    print('P04-P04-P04 PASS: actual dualScope short lease expiry, bound current Worker/fence, first USER source, temporary Vault SYSTEM recovery Audit + Job CANCELLED/Lease EXPIRED/Attempt JOB_CANCELLED atomic. Unexpired/old/wrong/success/repeat/unaudited refuse; postwrite Audit/recovery/identity faults rollback; revoked business still denied, safe recovery allowed; history/files/results retained. No OS kill, lost-ack proof, runner/HTTP or production claim.')


if __name__=='__main__':fixture.main(exercise=exercise)
