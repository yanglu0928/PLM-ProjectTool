"""Real commit-lost-ack and full fixed failure sources; never guessed from FAILED."""
from contextlib import contextmanager
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.audit.application.worker_termination import AuditExportWorkerTermination
from plm_assistant.modules.audit.application.verify_termination import AuditExportTerminationVerification
from plm_assistant.modules.audit.infrastructure.export_failure_proof import SqlAlchemyAuditExportFailureProof
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure

spec=spec_from_file_location('_failure_verify_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],queue=v['queue'],failure=failure,
        audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    owner=AuditExportWorkerTermination(**deps)
    verifier=AuditExportTerminationVerification(failure_proofs=SqlAlchemyAuditExportFailureProof(),**deps)
    tables=('job_jobs','job_leases','job_attempts','aud_export_results','doc_file_objects','aud_events','aud_exports','aud_export_acceptances')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def reject(c,reason='AUTH_ACCESS_DENIED',service=verifier):
        before=snapshot()
        try:service.verify(c,reason_code=reason)
        except AuditExportWorkerError:pass
        else:raise AssertionError('incomplete failure source accepted')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,_=v['prepare'](scope,0)
        reject(c)
        lost=[False]
        @contextmanager
        def lost_ack():
            with v['uow']() as tx:
                class Proxy:
                    def __getattr__(self,name):return getattr(tx,name)
                    def commit(self):
                        tx.commit()
                        assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('FAILED',)
                        lost[0]=True;raise RuntimeError('synthetic lost confirmation AFTER actual commit')
                yield Proxy()
        interrupted=AuditExportWorkerTermination(**(deps|{'unit_of_work':lost_ack}))
        try:interrupted.terminate(c,reason_code='AUTH_ACCESS_DENIED')
        except AuditExportWorkerError as exc:assert exc.code=='AUDIT_UNAVAILABLE'
        else:raise AssertionError('lost confirmation not injected')
        assert lost==[True]
        before=snapshot();receipt=verifier.verify(c,reason_code='AUTH_ACCESS_DENIED')
        assert receipt.failure.claim.job_id==c.job_id
        for _ in range(3):assert verifier.verify(c,reason_code='AUTH_ACCESS_DENIED')==receipt
        assert snapshot()==before
        reject(c,'LICENSE_OPERATION_DENIED')
        for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+1),replace(c,export_id=fixture.uuid4())):reject(wrong)
        # Real technical FAILED without Owner Audit is insufficient.
        accepted,c,_=v['prepare'](scope,0)
        with v['uow']() as tx:
            failure.fail_current(tx,request=v['submit']._queue_request(accepted.intent),refs=fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id),
                fencing_token=c.fencing_token,worker_ref=c.worker_ref,error_code='AUTH_ACCESS_DENIED',retryable=False);tx.commit()
        reject(c)
        # An actual wrongly bound Audit doesn't rescue technical status.
        with v['uow']() as tx:
            v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=accepted.intent.trace_id,event_scope=scope,
                target_project_id=accepted.intent.spec.project_id,actor_type='SYSTEM',actor_id=v['identity'],
                original_actor_id=accepted.intent.actor_id,actor_hint_digest=None,action='AUDIT_EXPORT_FAILED',outcome='FAILED',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=c.job_id,
                reason_code='LICENSE_OPERATION_DENIED',before_state='RUNNING',after_state='FAILED'));tx.commit()
        reject(c)
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);reject(c)
        accepted,c,_=v['prepare'](scope,0);owner.terminate(c,reason_code='AUTH_ACCESS_DENIED')
        with v['uow']() as tx:
            v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=accepted.intent.trace_id,event_scope=scope,
                target_project_id=accepted.intent.spec.project_id,actor_type='SYSTEM',actor_id=v['identity'],
                original_actor_id=accepted.intent.actor_id,actor_hint_digest=None,action='AUDIT_EXPORT_FAILED',outcome='FAILED',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=c.job_id,
                reason_code='AUTH_ACCESS_DENIED',before_state='RUNNING',after_state='FAILED'));tx.commit()
        reject(c)
    print('P04-P03-P03 PASS: actual dualScope commit THEN lost acknowledgement resolved only by full current-generation failure/Lease/Attempt+original pair and unique SYSTEM Audit; repeated reads eight-table snapshot unchanged; RUNNING/success/wrong generation or reason/technical FAILED without Audit/wrong Audit/duplicate Audit refuse. Read proof not production or runner wiring/cancel/retry completion.')


if __name__=='__main__':fixture.main(exercise=exercise)
