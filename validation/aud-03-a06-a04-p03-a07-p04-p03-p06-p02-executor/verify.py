"""Actual single-command lifecycle with bounded DB and real shared periodic heartbeat."""
from contextlib import contextmanager
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.audit.application.worker_execution import AuditExportWorkerExecution
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.run_export_once import AuditExportRunOnce
from plm_assistant.modules.audit.application.execute_export import AuditExportExecutor
from plm_assistant.modules.audit.application.read_execution_facts import AuditExportExecutionReader
from plm_assistant.modules.audit.application.worker_termination import AuditExportWorkerTermination
from plm_assistant.modules.audit.application.verify_termination import AuditExportTerminationVerification
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.verify_cancel import AuditExportCancelVerification
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.audit.application.verify_retry import AuditExportRetryVerification
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.infrastructure.export_cancel_proof import SqlAlchemyAuditExportCancelProof
from plm_assistant.modules.audit.infrastructure.export_failure_proof import SqlAlchemyAuditExportFailureProof
from plm_assistant.modules.audit.infrastructure.export_retry_proof import SqlAlchemyAuditExportRetryProof
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionRead
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal

spec=spec_from_file_location('_executor_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    database=create_worker_database_runtime(v['url']);db=v['db'];lost={'job':None,'state':None,'armed':False}
    @contextmanager
    def bounded_uow():
        with database.unit_of_work() as tx:
            class Proxy:
                session=tx.session
                def commit(self):
                    lose=lost['armed'] and self.session.scalar(text('SELECT state FROM plm.job_jobs WHERE job_id=:job'),{'job':lost['job']})==lost['state']
                    tx.commit()
                    if lose:lost['armed']=False;raise RuntimeError('synthetic confirmation loss AFTER actual commit')
            v['active'][0]+=1
            try:yield Proxy()
            finally:v['active'][0]-=1
    deps=dict(v['deps']);deps['unit_of_work']=bounded_uow
    worker=AuditExportWorkerExecution(files=v['files'],results=v['results'],completion=v['completion'],audit=v['audit'],system_actor=v['system_actor'],**deps)
    heartbeat=AuditExportWorkerHeartbeat(renewals=JobLeaseRenewal(repository=v['lease_repo']),**{k:deps[k] for k in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=AuditHeartbeatSupervisor(heartbeats=heartbeat,max_workers=1)
    runner=AuditExportRunOnce(worker=worker,supervisor=supervisor,lease_seconds=6,interval_seconds=.2)
    cancel_deps=dict(unit_of_work=bounded_uow,repository=v['repo'],cancellations=v['canceller'],sources=SqlAlchemyAuditExportCancelSources(),audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    failure_deps=dict(unit_of_work=bounded_uow,repository=v['repo'],queue=v['queue'],failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo']),audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    reader=AuditExportExecutionReader(execution_facts=AuditExportExecutionRead(queue=v['queue'],leases=v['lease_repo']),**cancel_deps)
    owner=AuditExportExecutor(runner=runner,reader=reader,termination=AuditExportWorkerTermination(**failure_deps),
        termination_verifier=AuditExportTerminationVerification(failure_proofs=SqlAlchemyAuditExportFailureProof(),**failure_deps),
        cancellation=AuditExportWorkerCancel(**cancel_deps),cancellation_verifier=AuditExportCancelVerification(completion_proofs=SqlAlchemyAuditExportCancelProof(),**cancel_deps),
        retry=AuditExportWorkerRetry(authority=deps['authority'],**failure_deps),retry_verifier=AuditExportRetryVerification(retry_proofs=SqlAlchemyAuditExportRetryProof(),authority=deps['authority'],**failure_deps),supervisor=supervisor)
    a=fixture.a
    requests=AuditExportCancelRequestService(unit_of_work=v['uow'],repository=v['repo'],
        authorization=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard']),
        cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=cancel_deps['sources'],audit=v['audit'])
    def request(accepted,scope):
        return requests.request(RequestAuditExportCancel(accepted.intent.export_id,scope,accepted.intent.spec.project_id,
            v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),'Synthetic executor cancellation'),idempotency_key=str(fixture.uuid4()))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def replay(c,expected):
        before=snapshot();assert owner.execute(c)==expected;assert snapshot()==before
    class RenderFault:
        def __init__(self,code):self.code=code
        def __getattr__(self,name):return getattr(worker,name)
        def render(self,c):raise AuditExportWorkerError(self.code)
    try:
        for scope in ('PROJECT','DEPLOYMENT'):
            for count in (0,260):
                accepted,c,_=v['prepare'](scope,count,capture_source=False,render_file=False)
                if count==0:lost.update(job=c.job_id,state='SUCCEEDED',armed=True)
                result=owner.execute(c);assert result.kind=='SUCCEEDED';assert not lost['armed'];replay(c,result)
                if count==0:
                    actor=accepted.intent.actor_id
                    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
                    before=snapshot()
                    try:owner.execute(c)
                    except AuditExportWorkerError as exc:assert exc.code=='AUTH_ACCESS_DENIED'
                    else:raise AssertionError('revoked published result exposed')
                    assert snapshot()==before
                    db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            # Actual revocation is safely FAILED, never business permission bypass.
            accepted,c,_=v['prepare'](scope,0,capture_source=False,render_file=False);actor=accepted.intent.actor_id
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            lost.update(job=c.job_id,state='FAILED',armed=True)
            result=owner.execute(c);assert result.kind=='FAILED' and not lost['armed'];replay(c,result)
            assert not db.execute('SELECT 1 FROM plm.aud_export_captures WHERE export_id=%s',(c.export_id,)).fetchone()
            db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            # Authorized cancellation before run, alive and actually expired, including commit lost ack.
            for expired in (False,True):
                accepted,c,_=v['prepare'](scope,0,seconds=2 if expired else 60,capture_source=False,render_file=False)
                request(accepted,scope)
                if expired:time.sleep(2.05)
                lost.update(job=c.job_id,state='CANCELLED',armed=True)
                result=owner.execute(c);assert result.kind=='CANCELLED' and result.value.expired is expired and not lost['armed'];replay(c,result)
            # Cancellation during the main synchronous render operation, real heartbeat stops first.
            accepted,c,_=v['prepare'](scope,0,capture_source=False,render_file=False)
            class CancelDuringRender:
                def __getattr__(self,name):return getattr(worker,name)
                def render(self,c):request(accepted,scope);return worker.render(c)
            runner._worker=CancelDuringRender()
            try:assert owner.execute(c).kind=='CANCELLED'
            finally:runner._worker=worker
            # Terminal content and transient failure take different actual Owner paths.
            for code,kind in (('AUDIT_EXPORT_CONTENT_UNAVAILABLE','FAILED'),('AUDIT_UNAVAILABLE','RETRY_SCHEDULED')):
                accepted,c,_=v['prepare'](scope,0,capture_source=False,render_file=False)
                runner._worker=RenderFault(code)
                lost.update(job=c.job_id,state='RETRY_WAIT' if kind=='RETRY_SCHEDULED' else 'FAILED',armed=True)
                try:result=owner.execute(c);assert result.kind==kind and not lost['armed'];replay(c,result)
                finally:runner._worker=worker
                if kind=='RETRY_SCHEDULED':
                    request(accepted,scope)  # Immediate cancellation while waiting preserves the completed retry receipt.
                    replay(c,result)
            # Naked technical cancellation cannot be turned into a proven outcome.
            accepted,c,_=v['prepare'](scope,0,capture_source=False,render_file=False)
            target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
            with v['uow']() as tx:
                v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic no USER source')
                v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref);tx.commit()
            before=snapshot()
            try:owner.execute(c)
            except AuditExportWorkerError:pass
            else:raise AssertionError('naked state became verified outcome')
            assert snapshot()==before
    finally:database.dispose()
    print('P06-P02 PASS: actual bounded PG/shared real periodic heartbeat dualScope fresh empty/260 success + no-write replay; User revocation safely FAILED without capture, authorized alive/expired/in-render cancellation; content terminal vs transient retry. Actual successful/FAILED/CANCELLED/RETRY_WAIT commits THEN confirmation loss resolved through real sources; six-table outcome replay unchanged, immediate waiting cancellation preserves original retry receipt, naked technical cancellation refused. No claim process loop/HTTP/production/package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
