"""Actual queue/claim/completion/cancel locks, caller rollback; synthetic Export/authority/marker."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Barrier,Event
from uuid import uuid4
import time
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef,AuditExportJobQueue
from plm_assistant.modules.jobs.infrastructure.audit_export_enqueue_repository import SqlAlchemyAuditExportJobQueueRepository
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellationTarget,AuditExportCancellation
from plm_assistant.modules.jobs.infrastructure.audit_export_cancel_repository import SqlAlchemyAuditExportCancellationRepository
from plm_assistant.modules.jobs.application.lease import JobLeaseService,JobLeaseError
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.audit.application.public import AuditService,AuditEventDraft
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository

load=spec_from_file_location('_completion_fixture',Path(__file__).resolve().parents[1]/'aud-02-a01-authorized-read'/'verify.py')
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime='jobcomplete_'+uuid4().hex[:12],None
    with f.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url=URL.create('postgresql+psycopg',username='poc_admin',host='127.0.0.1',port=55432,database=name)
            command.upgrade(create_migration_config(url),'head');runtime=create_database_runtime(url)
            queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository())
            repository=SqlAlchemyJobLeaseRepository();leases=JobLeaseService(unit_of_work=runtime.unit_of_work,repository=repository)
            completion=AuditExportJobCompletion(queue=queue,leases=repository)
            canceller=AuditExportCancellation(repository=SqlAlchemyAuditExportCancellationRepository())
            audit=AuditService(SqlAlchemyAuditRepository())
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,'Synthetic completion',b'c'*32,'DEPLOYMENT_ADMIN')
                project=f.schema.insert(db,'prj_projects',dict(project_code='COMPLETE',project_code_normalized='complete',name='Synthetic completion project',created_by=actor),'project_id')
                db.execute('CREATE TABLE public.synthetic_publications(job_id uuid PRIMARY KEY)')
                def target(scope='DEPLOYMENT'):
                    request=AuditExportJobRequest(uuid4(),actor,scope,project if scope=='PROJECT' else None,uuid4())
                    with runtime.unit_of_work() as tx:refs=queue.enqueue_export(tx,request=request);tx.commit()
                    return AuditExportCancellationTarget(request,refs)
                def claim(t,seconds=60):
                    value=leases.claim_next(worker_ref='worker',lease_seconds=seconds);assert value.job_id==t.refs.job_id
                    return dict(request=t.request,refs=t.refs,fencing_token=value.fencing_token,worker_ref='worker')
                def complete(args,marker=False):
                    with runtime.unit_of_work() as tx:
                        if marker:tx.session.execute(text('INSERT INTO public.synthetic_publications(job_id) VALUES(:job)'),dict(job=args['refs'].job_id))
                        value=completion.complete_current(tx,**args);tx.commit();return value
                def cancel(t):
                    with runtime.unit_of_work() as tx:value=canceller.request_cancel(tx,target=t,requested_by=actor,reason='Synthetic completion race');tx.commit();return value
                def snapshot():
                    return {table:tuple(db.execute(sql.SQL('SELECT * FROM {}.{} ORDER BY 1').format(sql.Identifier('public' if table=='synthetic_publications' else 'plm'),sql.Identifier(table)))) for table in ('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','aud_exports','aud_export_results','doc_file_objects','synthetic_publications')}
                def deny(action,code):
                    before=snapshot()
                    try:action()
                    except JobLeaseError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError('invalid completion accepted')
                    assert snapshot()==before
                for scope in ('PROJECT','DEPLOYMENT'):
                    t=target(scope);args=claim(t);value=complete(args)
                    assert value.job_id==t.refs.job_id
                    job=db.execute('SELECT state,lease_expires_at,completed_at FROM plm.job_jobs WHERE job_id=%s',(t.refs.job_id,)).fetchone()
                    lease=db.execute('SELECT state FROM plm.job_leases WHERE job_id=%s',(t.refs.job_id,)).fetchone()
                    attempt=db.execute('SELECT completed_at,error_code FROM plm.job_attempts WHERE job_id=%s',(t.refs.job_id,)).fetchone()
                    assert job[0:2]==('SUCCEEDED',None) and lease==('RELEASED',) and attempt==(job[2],None)
                    deny(lambda:complete(args),'STALE_LEASE')
                    assert not cancel(t).changed and cancel(t).state=='SUCCEEDED'
                t=target();args=claim(t)
                for changes,code in ((dict(worker_ref='other'),'STALE_LEASE'),(dict(fencing_token=args['fencing_token']+1),'STALE_LEASE'),(dict(refs=AuditExportJobRef(t.refs.job_id,uuid4())),'JOB_STORE_UNAVAILABLE'),(dict(request=replace(t.request,actor_id=uuid4())),'JOB_STORE_UNAVAILABLE'),(dict(request=replace(t.request,scope='PROJECT',project_id=project)),'JOB_STORE_UNAVAILABLE')):
                    deny(lambda changes=changes:complete(args|changes),code)
                # Actual technical Lease consistency, then restore; no guessing repaired metadata.
                db.execute("UPDATE plm.job_leases SET lease_expires_at=lease_expires_at+interval '1 second' WHERE job_id=%s",(t.refs.job_id,))
                deny(lambda:complete(args),'INCONSISTENT_LEASE')
                db.execute("UPDATE plm.job_leases SET lease_expires_at=lease_expires_at-interval '1 second' WHERE job_id=%s",(t.refs.job_id,))
                before=snapshot()
                try:
                    with runtime.unit_of_work() as tx:
                        audit.append(tx,AuditEventDraft(trace_id=t.request.trace_id,event_scope=t.request.scope,target_project_id=t.request.project_id,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,action='SYNTHETIC_COMPLETE',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=t.refs.job_id))
                        tx.session.execute(text('INSERT INTO public.synthetic_publications(job_id) VALUES(:job)'),dict(job=t.refs.job_id))
                        completion.complete_current(tx,**args)
                        assert tx.session.scalar(text('SELECT state FROM plm.job_jobs WHERE job_id=:job'),dict(job=t.refs.job_id))=='SUCCEEDED'
                        raise RuntimeError('synthetic caller post-completion fault')
                except RuntimeError:pass
                assert snapshot()==before
                # Returning from Port without caller commit must also roll back all changes.
                with runtime.unit_of_work() as tx:completion.complete_current(tx,**args)
                assert snapshot()==before
                complete(args)
                # Expiry between actual checkpoint and actual finish must fail at finish too.
                class SlowCheckpoint(SqlAlchemyJobLeaseRepository):
                    def check_current(self,tx,**kwargs):value=super().check_current(tx,**kwargs);time.sleep(1.15);return value
                t=target();args=claim(t,1);slow=AuditExportJobCompletion(queue=queue,leases=SlowCheckpoint())
                def slow_complete():
                    with runtime.unit_of_work() as tx:
                        tx.session.execute(text('INSERT INTO public.synthetic_publications(job_id) VALUES(:job)'),dict(job=t.refs.job_id))
                        slow.complete_current(tx,**args);tx.commit()
                deny(slow_complete,'STALE_LEASE')
                renewed=leases.claim_next(worker_ref='renewed',lease_seconds=60);assert renewed.job_id==t.refs.job_id
                complete(args|dict(fencing_token=renewed.fencing_token,worker_ref='renewed'))
                # Actual elapsed lease/takeover fences old Worker; new generation can complete.
                t=target();args=claim(t,1);time.sleep(1.15)
                deny(lambda:complete(args),'STALE_LEASE')
                nextclaim=leases.claim_next(worker_ref='next',lease_seconds=60);assert nextclaim.job_id==t.refs.job_id
                deny(lambda:complete(args),'STALE_LEASE')
                complete(args|dict(fencing_token=nextclaim.fencing_token,worker_ref='next'))
                # Two real first completions: one success, second stale; no repeated Job mutation.
                t=target();args=claim(t);barrier=Barrier(2)
                def competing(_):
                    barrier.wait()
                    try:return complete(args)
                    except JobLeaseError as exc:assert exc.code=='STALE_LEASE';return None
                with ThreadPoolExecutor(max_workers=2) as pool:pair=list(pool.map(competing,(0,1)))
                assert sum(v is not None for v in pair)==1
                # Lock competition in both actual orderings, observed through pg_stat_activity.
                for cancel_first in (True,False):
                    t=target();args=claim(t);ready=Event();pid=[]
                    def rival():
                        with runtime.unit_of_work() as tx:
                            pid.append(tx.session.scalar(text('SELECT pg_backend_pid()')));ready.set()
                            if cancel_first:
                                try:completion.complete_current(tx,**args)
                                except JobLeaseError as exc:assert exc.code=='STALE_LEASE';return None
                                raise AssertionError('cancelled job completed')
                            result=canceller.request_cancel(tx,target=t,requested_by=actor,reason='Synthetic race');tx.commit();return result
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        with runtime.unit_of_work() as tx:
                            if cancel_first:canceller.request_cancel(tx,target=t,requested_by=actor,reason='Synthetic race')
                            else:
                                tx.session.execute(text('INSERT INTO public.synthetic_publications(job_id) VALUES(:job)'),dict(job=t.refs.job_id))
                                completion.complete_current(tx,**args)
                            future=pool.submit(rival);assert ready.wait(3)
                            deadline=time.monotonic()+3
                            while time.monotonic()<deadline:
                                state=db.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',(pid[0],)).fetchone()
                                if state and state[0]=='Lock':break
                                time.sleep(.01)
                            else:raise AssertionError('actual rival lock wait not observed')
                            assert not future.done();tx.commit()
                        result=future.result(timeout=5)
                    if cancel_first:
                        assert result is None
                        assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(t.refs.job_id,)).fetchone()==('CANCEL_REQUESTED',)
                        assert not db.execute('SELECT 1 FROM public.synthetic_publications WHERE job_id=%s',(t.refs.job_id,)).fetchone()
                    else:
                        assert not result.changed and result.state=='SUCCEEDED'
                        assert db.execute('SELECT count(*) FROM public.synthetic_publications WHERE job_id=%s',(t.refs.job_id,)).fetchone()==(1,)
                # Pending/FAILED/CANCELLED lack active current lease; no revive or guessed original edges.
                t=target();args=dict(request=t.request,refs=t.refs,fencing_token=1,worker_ref='worker');deny(lambda:complete(args),'STALE_LEASE')
                cancel(t);deny(lambda:complete(args),'STALE_LEASE')
                t=target();args=claim(t)
                leases.retry_or_fail(job_id=t.refs.job_id,fencing_token=args['fencing_token'],worker_ref='worker',error_code='SYNTHETIC_FAIL',retryable=False)
                deny(lambda:complete(args),'STALE_LEASE')
                t=target();args=claim(t);db.execute('DELETE FROM plm.job_outbox_events WHERE event_id=%s',(t.refs.event_id,));deny(lambda:complete(args),'JOB_STORE_UNAVAILABLE')
            print('P03-A04-P01 PASS: actual dualScope Queue/Outbox/claim/current Lease -> caller-UOW Job SUCCEEDED/Lease RELEASED/Attempt completion; no commit and post-Audit/marker fault rollback; pair/binding/consistency/expiry/takeover/terminal deny; concurrent one completion; actual cancel-vs-complete blocking observed both orders. Export/current authority/result/File/SystemActor refs absent/synthetic, marker not Artifact; NOT complete Worker/file/Audit publication/HTTP proof.')
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__=='__main__':main()
