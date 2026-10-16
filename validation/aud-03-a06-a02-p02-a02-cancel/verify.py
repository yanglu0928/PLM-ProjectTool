"""Real owned queue/lease cancellation and publication race; synthetic Owner authority/marker."""
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
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellationTarget,AuditExportCancellation,AuditExportCancellationError
from plm_assistant.modules.jobs.infrastructure.audit_export_cancel_repository import SqlAlchemyAuditExportCancellationRepository
from plm_assistant.modules.jobs.application.lease import JobLeaseService,JobLeaseError
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.application.lease_checkpoint import JobLeaseCheckpoint

load=spec_from_file_location("_cancel_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="cancelcommand_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository())
            cancellation=AuditExportCancellation(repository=SqlAlchemyAuditExportCancellationRepository())
            repo=SqlAlchemyJobLeaseRepository();leases=JobLeaseService(unit_of_work=runtime.unit_of_work,repository=repo)
            checkpoint=JobLeaseCheckpoint(repository=repo)
            with f.schema.connect(name) as db:
                actors=[f.auth.user(db,f"Synthetic cancel actor {i}",bytes([i+1])*32,"DEPLOYMENT_ADMIN") for i in range(2)]
                project=f.schema.insert(db,"prj_projects",dict(project_code="CANCEL",project_code_normalized="cancel",name="Synthetic cancellation project",created_by=actors[0]),"project_id")
                db.execute("CREATE TABLE public.synthetic_publications(job_id uuid PRIMARY KEY)")
                def target(scope="DEPLOYMENT"):
                    req=AuditExportJobRequest(uuid4(),actors[0],scope,project if scope=="PROJECT" else None,uuid4())
                    with runtime.unit_of_work() as tx:
                        refs=queue.enqueue_export(tx,request=req);tx.commit()
                    return AuditExportCancellationTarget(req,refs)
                def invoke(method,t,**kwargs):
                    with runtime.unit_of_work() as tx:
                        result=getattr(cancellation,method)(tx,target=t,**kwargs);tx.commit();return result
                def cancel(t,**kwargs):return invoke("request_cancel",t,**(dict(requested_by=actors[0],reason="合成取消原因")|kwargs))
                def deny(action,code):
                    try:action()
                    except (AuditExportCancellationError,JobLeaseError) as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("invalid cancellation accepted")
                def row(t):return db.execute("SELECT state,cancel_requested_by,cancel_reason,cancel_requested_at,completed_at FROM plm.job_jobs WHERE job_id=%s",(t.refs.job_id,)).fetchone()
                def snapshot():
                    tables=("job_jobs","job_leases","job_attempts","job_outbox_events","aud_events","aud_exports","aud_export_acceptances")
                    return {table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in tables}
                def claim(t,seconds=60):
                    result=leases.claim_next(worker_ref="worker-current",lease_seconds=seconds)
                    assert result.job_id==t.refs.job_id
                    return dict(job_id=result.job_id,fencing_token=result.fencing_token,worker_ref="worker-current")
                def publish(tx,job):tx.session.execute(text("INSERT INTO public.synthetic_publications(job_id) VALUES(:job)"),dict(job=job.job_id))
                for scope in ("PROJECT","DEPLOYMENT"):
                    t=target(scope)
                    assert cancel(t).state=="CANCELLED"
                    original=row(t)
                    assert not cancel(t,requested_by=actors[1],reason="另一合成原因").changed and row(t)==original
                    assert leases.claim_next(worker_ref="worker",lease_seconds=60) is None
                t=target();before=snapshot()
                try:
                    with runtime.unit_of_work() as tx:
                        cancellation.request_cancel(tx,target=t,requested_by=actors[0],reason="合成回滚")
                        raise RuntimeError("synthetic caller audit failure")
                except RuntimeError:pass
                assert snapshot()==before
                # Real competing first cancel, one first requester retained.
                barrier=Barrier(2)
                def competing(index):barrier.wait();return cancel(t,requested_by=actors[index],reason=f"合成并发{index}")
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(competing,(0,1)))
                assert sum(r.changed for r in results)==1
                winning=next(i for i,r in enumerate(results) if r.changed)
                assert row(t)[1:3]==(actors[winning],f"合成并发{winning}")
                # Running cancellation keeps lease until actual cooperative acknowledgement.
                t=target();args=claim(t)
                assert cancel(t).state=="CANCEL_REQUESTED"
                deny(lambda:leases.finish(**args,publish=publish),"STALE_LEASE")
                with runtime.unit_of_work() as tx:deny(lambda:checkpoint.check_current(tx,**args),"STALE_LEASE")
                deny(lambda:invoke("acknowledge_cancel",t,fencing_token=args['fencing_token'],worker_ref="other-worker"),"STALE_LEASE")
                deny(lambda:invoke("acknowledge_cancel",t,fencing_token=args['fencing_token']+1,worker_ref="worker-current"),"STALE_LEASE")
                deny(lambda:invoke("recover_expired_cancel",t),"LEASE_NOT_EXPIRED")
                before=snapshot()
                try:
                    with runtime.unit_of_work() as tx:
                        cancellation.acknowledge_cancel(tx,target=t,fencing_token=args['fencing_token'],worker_ref="worker-current")
                        raise RuntimeError("synthetic completion audit failure")
                except RuntimeError:pass
                assert snapshot()==before
                assert invoke("acknowledge_cancel",t,fencing_token=args['fencing_token'],worker_ref="worker-current").state=="CANCELLED"
                assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s",(t.refs.job_id,)).fetchone()[0]=="RELEASED"
                assert db.execute("SELECT error_code FROM plm.job_attempts WHERE job_id=%s",(t.refs.job_id,)).fetchone()[0]=="JOB_CANCELLED"
                # Retry-wait cancels without reviving prior attempt or creating an active lease.
                t=target();args=claim(t)
                assert leases.retry_or_fail(**args,error_code="SYNTHETIC_RETRY",retryable=True)=="RETRY_WAIT"
                assert cancel(t).state=="CANCELLED"
                # Real expired lease can be recovered exactly once; no next-generation claim.
                t=target();args=claim(t,seconds=1);cancel(t);time.sleep(1.15)
                deny(lambda:invoke("acknowledge_cancel",t,fencing_token=args['fencing_token'],worker_ref="worker-current"),"STALE_LEASE")
                barrier=Barrier(2)
                def recovery(index):barrier.wait();return invoke("recover_expired_cancel",t)
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(recovery,(0,1)))
                assert sum(r.changed for r in results)==1 and all(r.state=="CANCELLED" for r in results)
                assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s",(t.refs.job_id,)).fetchone()[0]=="EXPIRED"
                assert leases.claim_next(worker_ref="successor",lease_seconds=60) is None
                # Real row-lock race with publication in each ordering. Marker is synthetic, not Artifact.
                for cancel_first in (True,False):
                    t=target();args=claim(t);ready=Event();pid=[]
                    def rival():
                        with runtime.unit_of_work() as tx:
                            pid.append(tx.session.scalar(text("SELECT pg_backend_pid()")));ready.set()
                            if cancel_first:
                                try:repo.finish(tx,**args)
                                except JobLeaseError as exc:assert exc.code=="STALE_LEASE";return None
                                raise AssertionError("cancelled Job published")
                            result=cancellation.request_cancel(tx,target=t,requested_by=actors[0],reason="合成发布竞争")
                            tx.commit();return result
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        with runtime.unit_of_work() as tx:
                            if cancel_first:cancellation.request_cancel(tx,target=t,requested_by=actors[0],reason="合成先取消")
                            else:publish(tx,repo.finish(tx,**args))
                            future=pool.submit(rival);assert ready.wait(3)
                            deadline=time.monotonic()+3
                            while not db.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid[0],)).fetchone()[0]:
                                assert time.monotonic()<deadline;time.sleep(.01)
                            tx.commit()
                        result=future.result(timeout=3)
                    if cancel_first:
                        assert row(t)[0]=="CANCEL_REQUESTED"
                        assert db.execute("SELECT count(*) FROM public.synthetic_publications WHERE job_id=%s",(t.refs.job_id,)).fetchone()[0]==0
                        invoke("acknowledge_cancel",t,fencing_token=args['fencing_token'],worker_ref="worker-current")
                    else:
                        assert result.state=="SUCCEEDED" and not result.changed
                        assert row(t)[1:] == (None,None,None,row(t)[4])
                        assert db.execute("SELECT count(*) FROM public.synthetic_publications WHERE job_id=%s",(t.refs.job_id,)).fetchone()[0]==1
                # Failure terminal is not revived and source corruption never auto-repaired.
                t=target();args=claim(t);leases.retry_or_fail(**args,error_code="SYNTHETIC_FAILURE",retryable=False)
                assert cancel(t).state=="FAILED" and not cancel(t).changed
                t=target();before=snapshot()
                wrong=[replace(t,refs=AuditExportJobRef(uuid4(),t.refs.event_id)),replace(t,refs=AuditExportJobRef(t.refs.job_id,uuid4())),replace(t,request=replace(t.request,actor_id=actors[1])),replace(t,request=replace(t.request,scope="PROJECT",project_id=project))]
                for bad in wrong:deny(lambda bad=bad:cancel(bad),"CONFLICT_STATE")
                assert snapshot()==before
                db.execute("DELETE FROM plm.job_outbox_events WHERE event_id=%s",(t.refs.event_id,));before=snapshot()
                deny(lambda:cancel(t),"CONFLICT_STATE");assert snapshot()==before
                # Legacy cancel state without first metadata is not guessed/backfilled.
                db.execute("UPDATE plm.job_jobs SET state='FAILED' WHERE job_id=%s",(t.refs.job_id,))
                legacy=target();db.execute("UPDATE plm.job_jobs SET state='CANCEL_REQUESTED' WHERE job_id=%s",(legacy.refs.job_id,));before=snapshot()
                deny(lambda:cancel(legacy),"CONFLICT_STATE");deny(lambda:invoke("recover_expired_cancel",legacy),"CONFLICT_STATE");assert snapshot()==before
            print("AUD-03-A06-A02-P02-A02 PASS: real pair/Scope/first-ref binding; pending/retry/running cancel; first requester immutable/concurrent single change; current Worker ack/rollback; real expired concurrent recovery; cancelled no claim; actual cancel-vs-finish blocking both orders and synthetic marker preserved; terminal/no repair/legacy deny. Owner Export/current authority/Audit/receipt synthetic or absent; NOT public cancellation/full Worker/Artifact")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
