"""Actual expired third attempt: atomic audited failure and true lost-ack proof."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.audit.application.worker_exhaustion import AuditExportWorkerExhaustion,EXHAUSTED_REASON
from plm_assistant.modules.audit.application.claim_export import AuditExportClaimAdmission
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims
from plm_assistant.modules.jobs.infrastructure.audit_export_claim_repository import SqlAlchemyAuditExportClaimRepository

spec=spec_from_file_location('_exhaustion_executor_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p06-p02-executor'/'verify.py')
e=module_from_spec(spec);spec.loader.exec_module(e);fixture=e.fixture


def exercise(v):
    database=e.create_worker_database_runtime(v['url']);db=v['db'];lost={'armed':False,'job':None}
    @contextmanager
    def uow():
        with database.unit_of_work() as tx:
            class Proxy:
                session=tx.session
                def commit(self):
                    lose=lost['armed'] and self.session.scalar(text('SELECT state FROM plm.job_jobs WHERE job_id=:job'),{'job':lost['job']})=='FAILED'
                    tx.commit()
                    if lose:lost['armed']=False;raise RuntimeError('synthetic AFTER actual commit')
            v['active'][0]+=1
            try:yield Proxy()
            finally:v['active'][0]-=1
    deps=dict(v['deps']);deps['unit_of_work']=uow
    worker=e.AuditExportWorkerExecution(files=v['files'],results=v['results'],completion=v['completion'],audit=v['audit'],system_actor=v['system_actor'],**deps)
    heartbeat=e.AuditExportWorkerHeartbeat(renewals=e.JobLeaseRenewal(repository=v['lease_repo']),**{k:deps[k] for k in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=e.AuditHeartbeatSupervisor(heartbeats=heartbeat,max_workers=1)
    failure=e.AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo'])
    fd=dict(unit_of_work=uow,repository=v['repo'],queue=v['queue'],failure=failure,audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    cd=dict(unit_of_work=uow,repository=v['repo'],cancellations=v['canceller'],sources=e.SqlAlchemyAuditExportCancelSources(),audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    exhaustion=AuditExportWorkerExhaustion(failure_proofs=e.SqlAlchemyAuditExportFailureProof(),**fd)
    reader=e.AuditExportExecutionReader(execution_facts=e.AuditExportExecutionRead(queue=v['queue'],leases=v['lease_repo']),**cd)
    executor=e.AuditExportExecutor(runner=e.AuditExportRunOnce(worker=worker,supervisor=supervisor,lease_seconds=6,interval_seconds=.2),reader=reader,
        termination=e.AuditExportWorkerTermination(**fd),termination_verifier=e.AuditExportTerminationVerification(failure_proofs=e.SqlAlchemyAuditExportFailureProof(),**fd),
        cancellation=e.AuditExportWorkerCancel(**cd),cancellation_verifier=e.AuditExportCancelVerification(completion_proofs=e.SqlAlchemyAuditExportCancelProof(),**cd),
        retry=e.AuditExportWorkerRetry(authority=deps['authority'],**fd),retry_verifier=e.AuditExportRetryVerification(retry_proofs=e.SqlAlchemyAuditExportRetryProof(),authority=deps['authority'],**fd),
        exhaustion=exhaustion,supervisor=supervisor)
    admission=AuditExportClaimAdmission(unit_of_work=uow,repository=v['repo'],queue=v['queue'],system_actor=v['system_actor'],supervisor=supervisor,
        claims=AuditExportClaims(repository=SqlAlchemyAuditExportClaimRepository()))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def reject(action):
        before=snapshot()
        try:action()
        except e.AuditExportWorkerError:pass
        else:raise AssertionError('invalid exhaustion accepted')
        assert snapshot()==before
    try:
        for scope in ('PROJECT','DEPLOYMENT'):
            a=fixture.a;now=datetime.now(timezone.utc)
            spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
            accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),spec),idempotency_key=str(fixture.uuid4()))
            first=admission.claim_next(worker_ref='exhaustion-first',lease_seconds=3)
            worker.capture(first.command);staged=worker.render(first.command)
            stage_locator,_=fixture.f._locators(staged.content.coordinate);stage_path=Path(v['file_root'])/stage_locator
            before_bytes=stage_path.read_bytes()
            reject(lambda:exhaustion.expire(first.command))
            time.sleep(3.05);second=admission.claim_next(worker_ref='exhaustion-second',lease_seconds=3)
            reject(lambda:exhaustion.expire(second.command))
            time.sleep(3.05);third=admission.claim_next(worker_ref='exhaustion-third',lease_seconds=3)
            assert third.claim.attempt_no==3
            reject(lambda:exhaustion.expire(third.command))
            time.sleep(3.05)
            reject(lambda:exhaustion.expire(first.command))
            from dataclasses import replace
            reject(lambda:exhaustion.expire(replace(third.command,worker_ref='wrong-worker')))
            class BrokenAudit:
                def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after actual audit')
            reject(lambda:AuditExportWorkerExhaustion(failure_proofs=e.SqlAlchemyAuditExportFailureProof(),**(fd|{'audit':BrokenAudit()})).expire(third.command))
            class BrokenFailure:
                def exhaustion(self,*args,**kwargs):
                    got=failure.exhaustion(*args,**kwargs)
                    if kwargs['mode']=='EXPIRE':raise RuntimeError('synthetic after actual state writes')
                    return got
            reject(lambda:AuditExportWorkerExhaustion(failure_proofs=e.SqlAlchemyAuditExportFailureProof(),**(fd|{'failure':BrokenFailure()})).expire(third.command))
            actor=accepted.intent.actor_id
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=False
            reject(lambda:worker.capture(third.command))
            lost.update(armed=True,job=third.command.job_id)
            result=executor.execute(third.command)
            assert result.kind=='FAILED' and not lost['armed'] and result.value.failure.claim.attempt_no==3
            before=snapshot();assert executor.execute(third.command)==result and exhaustion.verify(third.command)==result.value and snapshot()==before
            reject(lambda:exhaustion.expire(third.command))
            assert db.execute('SELECT state,lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(third.command.job_id,)).fetchone()==('FAILED',None)
            assert db.execute('SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=%s',(third.command.job_id,third.command.fencing_token)).fetchone()==('EXPIRED',)
            assert db.execute('SELECT error_code FROM plm.job_attempts WHERE job_id=%s AND fencing_token=%s',(third.command.job_id,third.command.fencing_token)).fetchone()==(EXHAUSTED_REASON,)
            assert Path(stage_path).read_bytes()==before_bytes
            db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=True
    finally:database.dispose()
    print('P06-P04 PASS: actual PostgreSQL dualScope three real expired attempts; alive/earlier/stale/wrong Worker refused, actual Audit/state-write rollback six tables, revoked User/License body denied but safety failure committed. Single-command executor recovers true commit-lost-ack and readonly receipt replay; old private bytes retained. No kill, sweep/process loop, production or installer proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
