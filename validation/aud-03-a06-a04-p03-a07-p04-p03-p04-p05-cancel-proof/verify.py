"""Actual commit-lost-ack for alive acknowledgement and expiry recovery."""
from contextlib import contextmanager
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.verify_cancel import AuditExportCancelVerification
from plm_assistant.modules.audit.infrastructure.export_cancel_proof import SqlAlchemyAuditExportCancelProof
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

spec=spec_from_file_location('_cancel_proof_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    a=fixture.a;db=v['db'];sources=SqlAlchemyAuditExportCancelSources()
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    requests=AuditExportCancelRequestService(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=sources,audit=v['audit'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=sources,audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    owner=AuditExportWorkerCancel(**deps)
    verifier=AuditExportCancelVerification(completion_proofs=SqlAlchemyAuditExportCancelProof(),**deps)
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects','aud_exports','aud_export_acceptances')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def request(accepted,scope):
        return requests.request(RequestAuditExportCancel(accepted.intent.export_id,scope,accepted.intent.spec.project_id,
            v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),'Synthetic authorized lost-ack request'),idempotency_key=str(fixture.uuid4()))
    def reject(c,expired=False,service=verifier):
        before=snapshot()
        try:service.verify(c,expired=expired)
        except AuditExportWorkerError:pass
        else:raise AssertionError('incomplete cancellation source accepted')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        for expired in (False,True):
            accepted,c,staged=v['prepare'](scope,0,seconds=2 if expired else 60)
            reject(c,expired);request(accepted,scope);reject(c,expired)
            if expired:time.sleep(2.05)
            lost=[False]
            @contextmanager
            def lost_ack():
                with v['uow']() as tx:
                    class Proxy:
                        def __getattr__(self,name):return getattr(tx,name)
                        def commit(self):
                            tx.commit()
                            assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('CANCELLED',)
                            lost[0]=True;raise RuntimeError('synthetic confirmation loss AFTER actual commit')
                    yield Proxy()
            interrupted=AuditExportWorkerCancel(**(deps|{'unit_of_work':lost_ack}))
            try:getattr(interrupted,'recover_expired' if expired else 'acknowledge')(c)
            except AuditExportWorkerError as exc:assert exc.code=='AUDIT_UNAVAILABLE'
            else:raise AssertionError('lost confirmation not injected')
            assert lost==[True]
            before=snapshot();receipt=verifier.verify(c,expired=expired)
            assert receipt.cancellation.job_id==c.job_id and receipt.expired is expired
            for _ in range(3):assert verifier.verify(c,expired=expired)==receipt
            assert snapshot()==before
            reject(c,not expired)
            for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+1),replace(c,export_id=fixture.uuid4())):reject(wrong,expired)
            class LostIdentity:
                count=0
                def assert_current(self):
                    self.count+=1
                    if self.count==2:raise RuntimeError('synthetic identity loss')
                    return v['system_actor'].assert_current()
            reject(c,expired,AuditExportCancelVerification(completion_proofs=SqlAlchemyAuditExportCancelProof(),**(deps|{'system_actor':LostIdentity()})))
            # Append actual duplicate completion source; unique receipt must now fail.
            with v['uow']() as tx:
                v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=accepted.intent.trace_id,event_scope=scope,
                    target_project_id=accepted.intent.spec.project_id,actor_type='SYSTEM',actor_id=v['identity'],
                    original_actor_id=accepted.intent.actor_id,actor_hint_digest=None,
                    action='AUDIT_EXPORT_CANCEL_RECOVERED' if expired else 'AUDIT_EXPORT_CANCELLED',outcome='SUCCESS',
                    target_owner_module='jobs',target_object_type='JOB-01',target_object_id=c.job_id,
                    reason_code='LEASE_EXPIRED' if expired else 'USER_REQUESTED',before_state='CANCEL_REQUESTED',after_state='CANCELLED'));tx.commit()
            reject(c,expired)
        accepted,c,_=v['prepare'](scope,0);request(accepted,scope)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref);tx.commit()
        reject(c)  # Real technical CANCELLED + first USER source, but no SYSTEM completion.
        accepted,c,_=v['prepare'](scope,0)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:
            v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic no USER source')
            v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref);tx.commit()
        reject(c)  # No immutable first USER source: never fabricate history.
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);reject(c)
    print('P04-P04-P05 PASS: actual dualScope alive ack and expired recovery commit THEN confirmation loss resolved only by current bound Job/Lease/Attempt + original first USER + unique actual SYSTEM completion sources; repeated reads eight tables unchanged. RUNNING/CANCEL_REQUESTED/success/wrong Worker/fence/root/mode/missing or duplicate completion/identity loss refuse; no mutation, commit, file read or STALE guess. No runner/HTTP/production proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
