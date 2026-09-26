"""Real audit-only claim, original pair admission and no silent exhaustion."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.claim_export import AuditExportClaimAdmission
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims
from plm_assistant.modules.jobs.infrastructure.audit_export_claim_repository import SqlAlchemyAuditExportClaimRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime

spec=spec_from_file_location('_claim_admission_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];database=create_worker_database_runtime(v['url'])
    claims=AuditExportClaims(repository=SqlAlchemyAuditExportClaimRepository())
    deps=dict(unit_of_work=database.unit_of_work,repository=v['repo'],claims=claims,queue=v['queue'],system_actor=v['system_actor'])
    def owner(**replace):return AuditExportClaimAdmission(supervisor=AuditHeartbeatSupervisor(heartbeats=object()),**(deps|replace))
    admission=owner();tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def pending(scope):
        a=fixture.a;now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),spec),idempotency_key=str(fixture.uuid4()))
    def retire(accepted,c=None):
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:
            v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic admission fixture finalization')
            if c:v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            tx.commit()
    def reject(service):
        before=snapshot()
        try:service.claim_next(worker_ref='admission-real')
        except AuditExportWorkerError:pass
        else:raise AssertionError('unbound claim committed')
        assert snapshot()==before
    try:
        # High-priority other Owner remains untouched throughout audit claims.
        foreign=fixture.uuid4()
        with v['uow']() as tx:
            tx.session.add(JobRow(job_id=foreign,owner_module='document',job_type='DOCUMENT_PARSE',scope='DEPLOYMENT',actor_ref=v['users'][1],
                trace_id=str(fixture.uuid4()),payload_refs={},idempotency_key=str(fixture.uuid4()),priority=1000,max_attempts=3));tx.commit()
        foreign_before=db.execute('SELECT * FROM plm.job_jobs WHERE job_id=%s',(foreign,)).fetchone()
        before=snapshot();assert admission.claim_next(worker_ref='admission-real') is None and snapshot()==before
        for scope in ('PROJECT','DEPLOYMENT'):
            accepted=pending(scope)
            class BrokenClaims:
                def peek_next(self,*args,**kwargs):return claims.peek_next(*args,**kwargs)
                def claim_target(self,*args,**kwargs):claims.claim_target(*args,**kwargs);raise RuntimeError('synthetic AFTER actual claim writes')
            reject(owner(claims=BrokenClaims()))
            class LostIdentity:
                count=0
                def assert_current(self):
                    self.count+=1
                    if self.count==2:raise RuntimeError('synthetic identity loss')
                    return v['system_actor'].assert_current()
            reject(owner(system_actor=LostIdentity()))
            got=admission.claim_next(worker_ref='admission-real');assert got.command.export_id==accepted.intent.export_id and got.claim.attempt_no==1
            v['worker'].capture(got.command);staged=v['worker'].render(got.command);v['worker'].publish(got.command,staged)
            before=snapshot();assert admission.claim_next(worker_ref='admission-real') is None and snapshot()==before
            # Actual authorized retry wait: cannot claim early; real deadline elapses.
            accepted=pending(scope);first=admission.claim_next(worker_ref='retry-worker')
            retry=AuditExportWorkerRetry(authority=v['worker']._authority,unit_of_work=database.unit_of_work,repository=v['repo'],queue=v['queue'],
                failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo']),audit=v['audit'],system_actor=v['system_actor'],supervisor=admission._supervisor)
            retry.retry(first.command,reason_code='AUDIT_UNAVAILABLE')
            before=snapshot();assert admission.claim_next(worker_ref='retry-new') is None and snapshot()==before
            time.sleep(5.05);second=admission.claim_next(worker_ref='retry-new')
            assert second.claim.job_id==accepted.job_id and second.claim.attempt_no==2
            retire(accepted,second.command)
            accepted=pending(scope)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda n:owner().claim_next(worker_ref=f'concurrent-{n}'),(1,2)))
            actual=[r for r in results if r is not None];assert len(actual)==1 and actual[0].claim.job_id==accepted.job_id
            retire(accepted,actual[0].command)
            # Actual short lease expires: reclaim into new Worker/fence, preserve old attempt.
            accepted=pending(scope);first=admission.claim_next(worker_ref='old-worker',lease_seconds=3)
            time.sleep(3.05);second=admission.claim_next(worker_ref='new-worker',lease_seconds=3)
            assert second.claim.job_id==first.claim.job_id and second.claim.attempt_no==2 and second.command.fencing_token==first.command.fencing_token+1
            assert db.execute('SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=%s',(first.claim.job_id,first.command.fencing_token)).fetchone()==('EXPIRED',)
            time.sleep(3.05);third=admission.claim_next(worker_ref='third-worker',lease_seconds=3);assert third.claim.attempt_no==3
            time.sleep(3.05);before=snapshot();assert admission.claim_next(worker_ref='fourth-worker') is None and snapshot()==before
            assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('RUNNING',)
            # Exclude this expired fixture without pretending audited exhaustion was implemented.
            target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
            with v['uow']() as tx:
                v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic exhausted fixture finalization')
                v['canceller'].recover_current_expired_cancel(tx,target=target,fencing_token=third.command.fencing_token,worker_ref=third.command.worker_ref);tx.commit()
        assert db.execute('SELECT * FROM plm.job_jobs WHERE job_id=%s',(foreign,)).fetchone()==foreign_before
        # Synthetic foreign fixture cleanup only: existing generic Job technical finish, not Document business PASS.
        claim=v['leases'].claim_next(worker_ref='foreign-fixture',lease_seconds=60);assert claim.job_id==foreign
        with v['uow']() as tx:v['lease_repo'].finish(tx,job_id=foreign,fencing_token=claim.fencing_token,worker_ref='foreign-fixture');tx.commit()
    finally:database.dispose()
    print('P06-P03 PASS: actual bounded PG dualScope PENDING audit-only admission, original Root/pair/current identity and current lease binding, capture/render/publish; high-priority foreign owner untouched, competing supervisors one claim, real expiry/new Worker-fence/Attempt, no fourth claim or silent FAILED. Actual claim-write fault/identity loss rollback six tables. Exhausted expiry finalization/claim lost-ack recovery/process loop remain pending; no production or package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
