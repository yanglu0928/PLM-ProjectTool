"""Actual commit THEN confirmation loss; immutable receipts survive next claim."""
from contextlib import contextmanager
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.audit.application.verify_retry import AuditExportRetryVerification
from plm_assistant.modules.audit.infrastructure.export_retry_proof import SqlAlchemyAuditExportRetryProof
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure

spec=spec_from_file_location('_retry_proof_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],queue=v['queue'],failure=failure,audit=v['audit'],
        authority=v['worker']._authority,system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    owner=AuditExportWorkerRetry(**deps)
    verifier=AuditExportRetryVerification(retry_proofs=SqlAlchemyAuditExportRetryProof(),**deps)
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects','aud_exports','aud_export_acceptances')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def reject(c,attempt=1,service=verifier):
        before=snapshot()
        try:service.verify(c,attempt_no=attempt)
        except AuditExportWorkerError:pass
        else:raise AssertionError('incomplete retry source accepted')
        assert snapshot()==before
    def read(c,attempt):
        before=snapshot();receipt=verifier.verify(c,attempt_no=attempt)
        for _ in range(3):assert verifier.verify(c,attempt_no=attempt)==receipt
        assert snapshot()==before;return receipt
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,_=v['prepare'](scope,0);reject(c);history=[]
        for attempt,delay in ((1,5),(2,15),(3,0)):
            lost=[False]
            @contextmanager
            def lost_ack():
                with v['uow']() as tx:
                    class Proxy:
                        def __getattr__(self,name):return getattr(tx,name)
                        def commit(self):
                            tx.commit();assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('FAILED' if attempt==3 else 'RETRY_WAIT',)
                            lost[0]=True;raise RuntimeError('synthetic confirmation loss AFTER actual commit')
                    yield Proxy()
            interrupted=AuditExportWorkerRetry(**(deps|{'unit_of_work':lost_ack}))
            try:interrupted.retry(c,reason_code='AUDIT_UNAVAILABLE')
            except AuditExportWorkerError as exc:assert exc.code=='AUDIT_UNAVAILABLE'
            else:raise AssertionError('lost ack not injected')
            assert lost==[True];receipt=read(c,attempt);history.append((c,attempt,receipt))
            assert receipt.transition.claim.fencing_token==c.fencing_token and receipt.transition.claim.attempt_no==attempt
            reject(c,attempt%3+1)
            for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+100),replace(c,export_id=fixture.uuid4())):reject(wrong,attempt)
            v['guard'].enabled=False;reject(c,attempt);v['guard'].enabled=True
            actor=accepted.intent.actor_id
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            reject(c,attempt)
            db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            class LostIdentity:
                count=0
                def assert_current(self):
                    self.count+=1
                    if self.count==2:raise RuntimeError('synthetic second identity loss')
                    return v['system_actor'].assert_current()
            reject(c,attempt,AuditExportRetryVerification(retry_proofs=SqlAlchemyAuditExportRetryProof(),**(deps|{'system_actor':LostIdentity()})))
            if delay:
                time.sleep(delay+.05)
                claim=v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60)
                assert claim.job_id==c.job_id and claim.attempt_no==attempt+1
                assert read(c,attempt)==receipt  # Current job is now RUNNING in a newer generation.
                c=replace(c,fencing_token=claim.fencing_token)
        for old,number,receipt in history:assert read(old,number)==receipt
        # Bare technical retry has no owned SYSTEM source and is never adopted.
        accepted,c,_=v['prepare'](scope,0)
        with v['uow']() as tx:
            failure.fail_current(tx,request=v['submit']._queue_request(accepted.intent),refs=fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id),
                fencing_token=c.fencing_token,worker_ref=c.worker_ref,error_code='AUDIT_UNAVAILABLE',retryable=True,delay_seconds=5);tx.commit()
        reject(c)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic fixture finalization');tx.commit()
        # Actual duplicate SYSTEM events BEFORE the conversion fall in the same attempt window.
        accepted,c,_=v['prepare'](scope,0)
        class DuplicateAudit:
            def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);return v['audit'].append(*args,**kwargs)
        AuditExportWorkerRetry(**(deps|{'audit':DuplicateAudit()})).retry(c,reason_code='AUDIT_UNAVAILABLE');reject(c)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic duplicate fixture finalization');tx.commit()
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);reject(c)
    print('P05-P02 PASS: real dualScope all three retry commits THEN confirmation loss, original attempt Lease/AUDIT_UNAVAILABLE+fixed deadlines+unique actual SYSTEM source; repeated eight-table reads unchanged, original receipts stable after real next claims and final FAILED. Wrong Worker/fence/root/attempt/license, running/success/missing/duplicate source reject. No mutation/file I/O/current-generation authority from historical receipt; no runner/production proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
