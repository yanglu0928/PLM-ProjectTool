"""True claim commit THEN fault; no new claim, guessed commit or body authority."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.claim_export import AuditExportClaimAdmission
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.infrastructure.audit_export_claim_repository import SqlAlchemyAuditExportClaimRepository
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime

spec=spec_from_file_location('_claim_confirmation_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    database=create_worker_database_runtime(v['url']);db=v['db'];fault={'mode':None,'commits':0}
    @contextmanager
    def uow():
        with database.unit_of_work() as tx:
            class Proxy:
                session=tx.session
                def commit(self):
                    fault['commits']+=1
                    mode=fault['mode'];fault['mode']=None
                    if mode=='before':raise RuntimeError('synthetic BEFORE actual commit')
                    tx.commit()
                    if mode=='after':raise RuntimeError('synthetic AFTER actual commit')
            yield Proxy()
    owner=AuditExportClaimAdmission(unit_of_work=uow,repository=v['repo'],claims=AuditExportClaims(repository=SqlAlchemyAuditExportClaimRepository()),
        queue=v['queue'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def pending(scope):
        a=fixture.a;now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,fixture.uuid4(),spec),idempotency_key=str(fixture.uuid4()))
    def reject(action):
        before=snapshot()
        try:action()
        except (AuditExportWorkerError,JobLeaseError):pass
        else:raise AssertionError('unconfirmed or stale claim accepted')
        assert snapshot()==before
    try:
        for scope in ('PROJECT','DEPLOYMENT'):
            accepted=pending(scope)
            fault.update(mode='before',commits=0)
            reject(lambda:owner.claim_next(worker_ref='confirmation-worker',lease_seconds=3))
            assert fault['commits']==1 and db.execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('PENDING',0)
            fault.update(mode='after',commits=0)
            got=owner.claim_next(worker_ref='confirmation-worker',lease_seconds=3)
            assert got.command.export_id==accepted.intent.export_id and got.claim.attempt_no==1 and fault['commits']==1
            for table in ('job_leases','job_attempts'):
                assert db.execute(sql.SQL('SELECT count(*) FROM plm.{} WHERE job_id=%s').format(sql.Identifier(table)),(got.command.job_id,)).fetchone()==(1,)
            identity=v['system_actor'].assert_current();before=snapshot()
            assert owner._confirm(got,identity)==got and owner._confirm(got,identity)==got and snapshot()==before
            reject(lambda:owner._confirm(replace(got,command=replace(got.command,worker_ref='wrong-worker')),identity))
            actor=accepted.intent.actor_id
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=False
            before=snapshot();assert owner._confirm(got,identity)==got and snapshot()==before
            reject(lambda:v['worker'].capture(got.command))
            db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=True
            time.sleep(3.05);reject(lambda:owner._confirm(got,identity))
            second=owner.claim_next(worker_ref='confirmation-new',lease_seconds=60)
            assert second.claim.attempt_no==2 and second.claim.job_id==got.claim.job_id
            reject(lambda:owner._confirm(got,identity))
            v['worker'].capture(second.command);staged=v['worker'].render(second.command);v['worker'].publish(second.command,staged)
            reject(lambda:owner._confirm(second,identity))
    finally:database.dispose()
    print('P06-P06 PASS: actual PG dualScope BEFORE commit rollback+refusal/no reclaim, actual commit THEN lost ack returns exact current claim with one Lease/Attempt; six-table readonly source rechecks/wrong Worker/expiry/new generation/success refusal. Revoked User/License does not block technical receipt but actual capture denied. New generation publishes normally. No real network interruption/cross-process unknown-command recovery/loop/production/package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
