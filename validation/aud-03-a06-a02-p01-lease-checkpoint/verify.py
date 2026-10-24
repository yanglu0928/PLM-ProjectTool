"""Actual PostgreSQL lease checkpoint; synthetic owner/payload and cancel states."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import time
import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL
from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.application.lease_checkpoint import JobLeaseCheckpoint
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


def connect(name):return psycopg.connect(host="127.0.0.1",port=55432,user="poc_admin",dbname=name,autocommit=True)


def main():
    name,runtime="leasecheck_"+uuid4().hex[:12],None
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            repo=SqlAlchemyJobLeaseRepository()
            leases=JobLeaseService(unit_of_work=runtime.unit_of_work,repository=repo)
            checkpoint=JobLeaseCheckpoint(repository=repo)
            identity=uuid4()
            with runtime.unit_of_work() as tx:
                tx.session.add(JobRow(job_id=identity,owner_module="audit",job_type="AUDIT_EXPORT",scope="DEPLOYMENT",trace_id=str(uuid4()),payload_refs={"export_id":str(uuid4()),"policy_version":"AUDIT-EXPORT-POLICY-V1"},idempotency_key="synthetic-checkpoint",max_attempts=3))
                tx.commit()
            claim=leases.claim_next(worker_ref="worker-first",lease_seconds=60)
            assert claim.job_id==identity and claim.fencing_token==1
            args=dict(job_id=identity,fencing_token=1,worker_ref="worker-first")
            def check(**overrides):
                with runtime.unit_of_work() as tx:return checkpoint.check_current(tx,**(args|overrides))
            def deny(code="STALE_LEASE",**overrides):
                try:check(**overrides)
                except JobLeaseError as exc:assert exc.code==code,(exc.code,code)
                else:raise AssertionError("stale/inconsistent checkpoint accepted")
            with connect(name) as db:
                tables=("job_jobs","job_leases","job_attempts","aud_exports","aud_export_acceptances","aud_events")
                def snapshot():return {table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in tables}
                before=snapshot()
                assert check()==claim
                deny(worker_ref="worker-other");deny(fencing_token=2);deny(job_id=uuid4())
                assert snapshot()==before
                def rival(table):
                    with connect(name) as other:
                        other.execute("SET lock_timeout='100ms'")
                        try:
                            with other.transaction():other.execute(sql.SQL("SELECT 1 FROM plm.{} WHERE job_id=%s FOR UPDATE").format(sql.Identifier(table)),(identity,))
                        except psycopg.errors.LockNotAvailable:return True
                        return False
                # Locks on all three facts survive return until caller UOW ends.
                with runtime.unit_of_work() as tx:
                    assert checkpoint.check_current(tx,**args)==claim
                    with ThreadPoolExecutor(max_workers=1) as pool:assert all(pool.map(rival,tables[:3]))
                    assert checkpoint.check_current(tx,**args)==claim
                with ThreadPoolExecutor(max_workers=1) as pool:assert not any(pool.map(rival,tables[:3]))
                try:
                    with runtime.unit_of_work() as tx:
                        checkpoint.check_current(tx,**args)
                        raise RuntimeError("synthetic caller failure")
                except RuntimeError:pass
                assert snapshot()==before
                # Synthetic corruption/retracted states; not a real cancel command implementation.
                for state in ("CANCEL_REQUESTED","CANCELLED","SUCCEEDED","FAILED","RETRY_WAIT","PENDING"):
                    db.execute("UPDATE plm.job_jobs SET state=%s WHERE job_id=%s",(state,identity))
                    marked=snapshot();deny();assert snapshot()==marked
                db.execute("UPDATE plm.job_jobs SET state='RUNNING' WHERE job_id=%s",(identity,))
                db.execute("UPDATE plm.job_jobs SET attempt_count=2 WHERE job_id=%s",(identity,))
                deny("INCONSISTENT_LEASE")
                db.execute("UPDATE plm.job_jobs SET attempt_count=1,lease_expires_at=lease_expires_at+interval '1 second' WHERE job_id=%s",(identity,))
                deny("INCONSISTENT_LEASE")
                db.execute("UPDATE plm.job_jobs SET lease_expires_at=lease_expires_at-interval '1 second' WHERE job_id=%s",(identity,))
                db.execute("UPDATE plm.job_attempts SET completed_at=clock_timestamp() WHERE job_id=%s",(identity,))
                deny()
                db.execute("UPDATE plm.job_attempts SET completed_at=NULL WHERE job_id=%s",(identity,))
                assert check()==claim
                # Real expiry, then real take-over increments fencing token and attempt.
                leases.heartbeat(**args,lease_seconds=1)
                time.sleep(1.15)
                expired=snapshot();deny();assert snapshot()==expired
                successor=leases.claim_next(worker_ref="worker-second",lease_seconds=60)
                assert successor.job_id==identity and successor.fencing_token==2 and successor.attempt_no==2
                deny()
                args=dict(job_id=identity,fencing_token=2,worker_ref="worker-second")
                assert check()==successor
                leases.finish(**args,publish=lambda tx,job:None)
                ended=snapshot();deny();assert snapshot()==ended
            print("AUD-03-A06-A02-P01 PASS: actual caller-UOW read-only current lease/worker/fence and expiry; all three locks held after return; rollback/no renewal/no completion; real expired takeover and terminal finish reject old worker; inconsistent attempt/time and synthetic cancel states deny. NOT cancel command/accepted Export/current authority/capture/file publication")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
