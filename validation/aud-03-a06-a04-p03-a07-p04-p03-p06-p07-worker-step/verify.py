"""Actual PENDING -> owned single step -> publication, stop does not claim."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.audit.application.worker_step import AuditExportWorkerStep
from plm_assistant.modules.audit.application.sweep_exhausted_export import AuditExportExhaustionSweep
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCandidates
from plm_assistant.modules.jobs.infrastructure.audit_export_exhaustion_scan_repository import SqlAlchemyAuditExportExhaustionScanRepository

spec=spec_from_file_location('_step_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p06-p04-exhaustion'/'verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p);e=p.e;fixture=p.fixture


def exercise(v):
    database=e.create_worker_database_runtime(v['url']);db=v['db']
    @contextmanager
    def uow():
        with database.unit_of_work() as tx:
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    deps=dict(v['deps']);deps['unit_of_work']=uow
    worker=e.AuditExportWorkerExecution(files=v['files'],results=v['results'],completion=v['completion'],audit=v['audit'],system_actor=v['system_actor'],**deps)
    heartbeat=e.AuditExportWorkerHeartbeat(renewals=e.JobLeaseRenewal(repository=v['lease_repo']),**{k:deps[k] for k in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=e.AuditHeartbeatSupervisor(heartbeats=heartbeat,max_workers=1)
    fd=dict(unit_of_work=uow,repository=v['repo'],queue=v['queue'],failure=e.AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo']),audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    cd=dict(unit_of_work=uow,repository=v['repo'],cancellations=v['canceller'],sources=e.SqlAlchemyAuditExportCancelSources(),audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    exhaustion=p.AuditExportWorkerExhaustion(failure_proofs=e.SqlAlchemyAuditExportFailureProof(),**fd)
    executor=e.AuditExportExecutor(runner=e.AuditExportRunOnce(worker=worker,supervisor=supervisor,lease_seconds=6,interval_seconds=.2),
        reader=e.AuditExportExecutionReader(execution_facts=e.AuditExportExecutionRead(queue=v['queue'],leases=v['lease_repo']),**cd),
        termination=e.AuditExportWorkerTermination(**fd),termination_verifier=e.AuditExportTerminationVerification(failure_proofs=e.SqlAlchemyAuditExportFailureProof(),**fd),
        cancellation=e.AuditExportWorkerCancel(**cd),cancellation_verifier=e.AuditExportCancelVerification(completion_proofs=e.SqlAlchemyAuditExportCancelProof(),**cd),
        retry=e.AuditExportWorkerRetry(authority=deps['authority'],**fd),retry_verifier=e.AuditExportRetryVerification(retry_proofs=e.SqlAlchemyAuditExportRetryProof(),authority=deps['authority'],**fd),exhaustion=exhaustion,supervisor=supervisor)
    admission=p.AuditExportClaimAdmission(unit_of_work=uow,repository=v['repo'],queue=v['queue'],system_actor=v['system_actor'],supervisor=supervisor,
        claims=p.AuditExportClaims(repository=p.SqlAlchemyAuditExportClaimRepository()))
    sweep=AuditExportExhaustionSweep(unit_of_work=uow,candidates=AuditExportExhaustionCandidates(repository=SqlAlchemyAuditExportExhaustionScanRepository()),system_actor=v['system_actor'],exhaustion=exhaustion)
    def new_step():return AuditExportWorkerStep(admission=admission,executor=executor,sweep=sweep,worker_ref='step-real')
    def pending(scope):
        a=fixture.a;now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),spec),idempotency_key=str(fixture.uuid4()))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    try:
        for scope in ('PROJECT','DEPLOYMENT'):
            step=new_step();before=snapshot();assert step.step().kind=='IDLE' and snapshot()==before
            accepted=pending(scope);step.request_stop();before=snapshot();assert step.step().kind=='STOPPED' and snapshot()==before
            step=new_step();result=step.step();assert result.kind=='EXECUTED' and result.value.kind=='SUCCEEDED' and result.value.command.export_id==accepted.intent.export_id
            before=snapshot();assert step.step().kind=='IDLE' and snapshot()==before
            accepted=pending(scope);actor=accepted.intent.actor_id
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            result=step.step();assert result.value.kind=='FAILED' and result.value.command.export_id==accepted.intent.export_id
            db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
    finally:database.dispose()
    print('P06-P07 PASS: actual bounded PG dualScope real pending admission/shared periodic heartbeat/single-step publication; empty and stop do not write/claim, revoked current User safely fails without body. Scheduling alternation, pending timeout drain and local-only expired hint release unit tested; no process loop/fair multiworker/production/package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
