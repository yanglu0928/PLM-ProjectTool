"""Read actual third Worker failure through owned Ports, no new user generation."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
from psycopg import sql
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobSources
from plm_assistant.modules.jobs.infrastructure.audit_user_retry_source import SqlAlchemyAuditUserRetryJobSources
from plm_assistant.modules.audit.application.user_retry_source import AuditUserRetrySourceReader
from plm_assistant.modules.audit.infrastructure.user_retry_failure_source import SqlAlchemyAuditUserRetryFailureSources
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

spec=spec_from_file_location('_user_retry_actual_worker',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p05-worker-retry'/'verify.py')
worker=module_from_spec(spec);spec.loader.exec_module(worker)

def observe(v,accepted,c):
    db=v['db']
    reader=AuditUserRetrySourceReader(repository=v['repo'],jobs=AuditUserRetryJobSources(queue=v['queue'],
        repository=SqlAlchemyAuditUserRetryJobSources()),failures=SqlAlchemyAuditUserRetryFailureSources())
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','aud_exports','aud_export_acceptances',
        'aud_export_retry_generations','plt_idempotency_receipts','doc_file_objects','aud_export_results')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    version=db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()[0]
    before=snapshot()
    with v['uow']() as tx:
        result=reader.read(tx,accepted=accepted,expected_version=version)
    assert result.accepted==accepted and result.failure.attempt_no==3
    assert result.failure.lock_version==version and result.failure.job_id==accepted.job_id
    assert db.execute('SELECT action,reason_code,after_state FROM plm.aud_events WHERE audit_event_id=%s',
        (result.failure_event_id,)).fetchone()==('AUDIT_EXPORT_FAILED','AUDIT_UNAVAILABLE','FAILED')
    assert snapshot()==before
    with v['uow']() as tx:
        bad_window=replace(result.failure,started_at=result.failure.completed_at+timedelta(seconds=1),
            completed_at=result.failure.completed_at+timedelta(seconds=2))
        try:SqlAlchemyAuditUserRetryFailureSources().read_failure(tx,accepted=accepted,failure=bad_window)
        except AuditExportWorkerError:pass
        else:raise AssertionError('Failure outside actual Attempt window accepted')
    assert snapshot()==before
    def reject(item,expected,code=None):
        before=snapshot()
        try:
            with v['uow']() as tx:reader.read(tx,accepted=item,expected_version=expected)
        except (JobLeaseError,AuditExportWorkerError) as exc:
            if code is not None:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('Invalid retry source accepted')
        assert snapshot()==before
    reject(accepted,version+1,'VERSION_CONFLICT')
    reject(accepted,True,'VALIDATION_FAILED')
    reject(replace(accepted,job_id=uuid4()),version)
    reject(replace(accepted,event_id=uuid4()),version)
    reject(replace(accepted,intent=replace(accepted.intent,actor_id=uuid4())),version)
    # A duplicate immutable historical event must make the source ambiguous, not
    # select a convenient row. The actual insertion is rolled back with this UOW.
    before=snapshot()
    with v['uow']() as tx:
        v['audit'].append(tx,worker.fixture.w.AuditEventDraft(trace_id=accepted.intent.trace_id,
            event_scope=accepted.intent.spec.scope,target_project_id=accepted.intent.spec.project_id,
            actor_type='SYSTEM',actor_id=v['system_actor'].assert_current(),original_actor_id=accepted.intent.actor_id,
            actor_hint_digest=None,action='AUDIT_EXPORT_FAILED',outcome='FAILED',
            target_owner_module='jobs',target_object_type='JOB-01',target_object_id=accepted.job_id,
            reason_code='AUDIT_UNAVAILABLE',before_state='RUNNING',after_state='FAILED'))
        try:reader.read(tx,accepted=accepted,expected_version=version)
        except AuditExportWorkerError:pass
        else:raise AssertionError('Ambiguous failure Audit accepted')
    assert snapshot()==before
    pending=v['submit'].submit_idempotent(worker.fixture.a.AuditExportSubmitAuthorizationRequest(
        v['tokens'][0 if accepted.intent.spec.scope=='PROJECT' else 1],worker.fixture.base.auth.CSRF,
        uuid4(),accepted.intent.spec),idempotency_key=str(uuid4()))
    reject(pending,0,'JOB_NOT_RETRYABLE')
    db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp()+interval '1 year' WHERE job_id=%s",(pending.job_id,))
    assert db.execute('SELECT count(*) FROM plm.aud_export_retry_generations').fetchone()==(0,)
    print('User retry source PASS: real Worker third bounded AUDIT_UNAVAILABLE failure/RELEASED Lease/Attempt/current version and unique original SYSTEM failure Audit read through Jobs/Audit owned Ports; wrong version/type/actor/pair and PENDING refuse, eleven tables unchanged. No current Session/CSRF/License user command/new generation/HTTP/production/Gate proof.')

if __name__=='__main__':worker.fixture.main(exercise=lambda v:worker.exercise(v,observe_failed=observe))
