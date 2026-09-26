"""Actual Owner/current authority/pair/lease -> atomic renewal; no scheduler."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal

spec=spec_from_file_location('_heartbeat_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    renewals=JobLeaseRenewal(repository=v['lease_repo'])
    deps={key:v['deps'][key] for key in ('unit_of_work','repository','authority','queue','leases','captures')}
    heartbeat=AuditExportWorkerHeartbeat(renewals=renewals,**deps)
    db=v['db']
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_exports',
            'aud_export_acceptances','aud_export_members','aud_export_captures','aud_export_render_attempts',
            'aud_export_results','doc_file_objects','doc_file_state_events','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def denied(command,code):
        before=snapshot()
        try:heartbeat.heartbeat(command,lease_seconds=600)
        except AuditExportWorkerError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unauthorized heartbeat accepted')
        assert snapshot()==before and v['active'][0]==0
    previous_export=None
    for scope in ('PROJECT','DEPLOYMENT'):
        _,command,staged=v['prepare'](scope,0)
        before=snapshot()
        old=db.execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]
        for stage in ('CAPTURE','RENDER','PUBLISH'):
            value=heartbeat.heartbeat(command,lease_seconds=600,stage=stage)
            assert value.job_id==command.job_id and value.fencing_token==command.fencing_token
        assert db.execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]>old
        after=snapshot()
        for table in tables:
            if table not in ('job_jobs','job_leases'):assert before[table]==after[table]
        actor=v['users'][0 if scope=='PROJECT' else 1]
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        denied(command,'AUTH_ACCESS_DENIED')
        db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        if scope=='PROJECT':
            db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            denied(command,'RESOURCE_NOT_FOUND')
            db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        else:
            db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            denied(command,'AUTH_ACCESS_DENIED')
            db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        v['guard'].enabled=False;denied(command,'LICENSE_OPERATION_DENIED');v['guard'].enabled=True
        denied(replace(command,worker_ref='wrong-worker'),'STALE_LEASE')
        if previous_export is not None:
            denied(replace(command,export_id=previous_export),'AUDIT_UNAVAILABLE')
        previous_export=command.export_id
        # Real renewal write, then later caller failure: all expiry writes roll back.
        class FailAfter:
            def renew_current(self,*args,**kwargs):
                renewals.renew_current(*args,**kwargs)
                raise RuntimeError('synthetic postrenew failure')
        heartbeat._renewals=FailAfter();denied(command,'AUDIT_UNAVAILABLE');heartbeat._renewals=renewals
        class RevokeAfter:
            def renew_current(self,*args,**kwargs):
                result=renewals.renew_current(*args,**kwargs);v['guard'].enabled=False;return result
        heartbeat._renewals=RevokeAfter();denied(command,'LICENSE_OPERATION_DENIED')
        heartbeat._renewals=renewals;v['guard'].enabled=True
        v['worker'].publish(command,staged);denied(command,'STALE_LEASE')
    accepted,command,_=v['prepare']()
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic heartbeat cancellation');tx.commit()
    denied(command,'STALE_LEASE')
    accepted,command,_=v['prepare'](seconds=2);time.sleep(2.05)
    denied(command,'STALE_LEASE')
    takeover=v['leases'].claim_next(worker_ref='heartbeat-takeover',lease_seconds=60)
    assert takeover.job_id==command.job_id
    denied(command,'STALE_LEASE')
    current=replace(command,fencing_token=takeover.fencing_token,worker_ref='heartbeat-takeover')
    assert heartbeat.heartbeat(current,lease_seconds=600)==takeover
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic heartbeat takeover retirement')
        v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=takeover.fencing_token,worker_ref='heartbeat-takeover');tx.commit()
    print('P03-A07-P02 PASS: actual original accepted Root/pair/current User/PM or Admin/License and Job/Lease/Attempt short-UOW heartbeat dualScope/all original stages, no source/result/Audit writes; User/role/license/wrong Worker/cancel/success/actual expiry/takeover old generation denied, new generation only renews; actual renewal postwrite failure and after-renew License denial roll back expiry. License synthetic; periodic scheduler/long-task coordination/production/three-platform/package remain pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
