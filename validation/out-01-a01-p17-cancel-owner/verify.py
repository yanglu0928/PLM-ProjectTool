"""Direct PostgreSQL 18 integration for the OutputRequest cancellation owner."""
from __future__ import annotations
import argparse,hashlib,json,re,sys,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import psycopg
from sqlalchemy import URL,text
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps"/"backend"/"src"))
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobQueue
from plm_assistant.modules.jobs.application.output_cancel import OutputJobCancellation
from plm_assistant.modules.jobs.infrastructure.output_enqueue_repository import SqlAlchemyOutputJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.output_cancel_repository import SqlAlchemyOutputJobCancellationRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow,JobLeaseRow,JobRow
from plm_assistant.modules.output.application.create_request import CreateOutputRequest,OutputRequestService,ResolvedOutputContext
from plm_assistant.modules.output.application.cancel_request import (
    CancelOutputRequest,OutputRequestCancelError,OutputRequestCancelService)
from plm_assistant.modules.output.infrastructure.create_request_repository import SqlAlchemyOutputRequestRepository
from plm_assistant.modules.output.infrastructure.cancel_request_repository import SqlAlchemyOutputRequestCancelRepository
from plm_assistant.modules.output.infrastructure.orm import OutputRequestRow
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow
def url(name,port):return URL.create("postgresql+psycopg",username="postgres",host="127.0.0.1",port=port,database=name)
def dsn(name,port):return f"postgresql://postgres@127.0.0.1:{port}/{name}"
def create_db(admin,name):
    with psycopg.connect(admin,autocommit=True) as c:c.execute(f'CREATE DATABASE "{name}" TEMPLATE postgres')
def drop_db(admin,name):
    with psycopg.connect(admin,autocommit=True) as c:c.execute(f'DROP DATABASE IF EXISTS "{name}"')
class CreateAccess:
    def __init__(self,actor):self.actor=actor
    def authorized_creator(self,*_,**__):return self.actor
class Access:
    def __init__(self,actor,allowed=True):self.actor,self.allowed=actor,allowed
    def authenticated_user(self,*_,**__):return self.actor
    def require_canceller(self,*_,**__):return self.allowed
class License:
    def require_valid(self,**_):return True
class Resolver:
    def resolve(self,transaction,*,actor_id,command):
        payload={"source_order":[str(v) for v in command.source_version_refs],"synthetic":True}
        return ResolvedOutputContext(command.source_version_refs,payload,canonical_payload_fingerprint(payload))
class FailAudit:
    def append(self,*_):raise RuntimeError("synthetic audit failure")
def make_creator(runtime,actor):
    return OutputRequestService(unit_of_work=runtime.unit_of_work,access=CreateAccess(actor),
        license_guard=License(),resolver=Resolver(),repository=SqlAlchemyOutputRequestRepository(),
        jobs=OutputJobQueue(SqlAlchemyOutputJobQueueRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(),audit=AuditService(SqlAlchemyAuditRepository()))
def make_canceller(runtime,actor,allowed=True,audit=None):
    return OutputRequestCancelService(unit_of_work=runtime.unit_of_work,access=Access(actor,allowed),
        license_guard=License(),repository=SqlAlchemyOutputRequestCancelRepository(),
        jobs=OutputJobCancellation(SqlAlchemyOutputJobCancellationRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(),audit=audit or AuditService(SqlAlchemyAuditRepository()))
def create_request(owner,project,key):
    src,template,trace=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    command=CreateOutputRequest(b"\x11"*32,b"\x22"*32,trace,project,"DOCX",
        template,(src,),"standard-output.v1","word.generate")
    return owner.create(command,idempotency_key=key)
def get_facts(runtime,project,request):
    with runtime.unit_of_work() as tx:
        return SqlAlchemyOutputRequestCancelRepository().get_for_update(
            tx,project_id=project,output_request_id=request)
def cmd(actor,project,request,version,reason="synthetic cancel reason"):
    return CancelOutputRequest(hashlib.sha256(actor.bytes).digest(),
        hashlib.sha256(b"csrf"+actor.bytes).digest(),uuid.uuid4(),project,request,reason,version)
def state(database,port,request):
    with psycopg.connect(dsn(database,port)) as c:
        o=c.execute("SELECT project_id,request_state,lock_version,completed_at,job_ref,context_snapshot_id "
                    "FROM plm.out_output_requests WHERE output_request_id=%s",(request,)).fetchone()
        j=c.execute("SELECT project_id,state,lock_version,cancel_requested_by,cancel_reason,cancel_requested_at,"
                    "completed_at,owner_module,job_type,payload_refs FROM plm.job_jobs WHERE job_id=%s",
                    (o[4],)).fetchone()
        audits=c.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='OUTPUT_REQUEST_CANCEL'",
                         (request,)).fetchone()[0]
        receipts=c.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                           "WHERE operation='V1_OUTPUT_REQUEST_CANCEL' AND result_ref_id=%s",(request,)).fetchone()[0]
        now=c.execute("SELECT clock_timestamp()").fetchone()[0]
        return o,j,audits,receipts,now
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--port",type=int,required=True)
    parser.add_argument("--run-id",required=True);args=parser.parse_args()
    if not 1<=args.port<=65535 or not re.fullmatch(r"[0-9]{1,12}",args.run_id):
        raise ValueError("temporary loopback PG and numeric hosted run ID required")
    db="plm_out17_"+args.run_id[-10:];admin=dsn("postgres",args.port);created=False;runtime=None
    result={"status":"PENDING","customer_data":False,"external_api_calls":0,
            "database":"isolated synthetic PostgreSQL 18.6"}
    try:
        create_db(admin,db);created=True;upgrade_database(url(db,args.port),"head")
        runtime=create_database_runtime(url(db,args.port))
        actor,manager,project,other=[uuid.uuid4() for _ in range(4)]
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=actor,username_display="p17-synthetic-actor",
                    username_normalized="p17-synthetic-actor",state="DISABLED",deployment_role="NONE"),
                UserRow(user_id=manager,username_display="p17-synthetic-manager",
                    username_normalized="p17-synthetic-manager",state="DISABLED",deployment_role="NONE"),
                ProjectRow(project_id=project,project_code="P17-A",project_code_normalized="P17-A",
                    name="Synthetic Output Cancel A",created_by=actor),
                ProjectRow(project_id=other,project_code="P17-B",project_code_normalized="P17-B",
                    name="Synthetic Output Cancel B",created_by=manager)])
            tx.commit()
        create=make_creator(runtime,actor);owner=make_canceller(runtime,actor)
        first=create_request(create,project,"p17-create-pending-00001")
        first_facts=get_facts(runtime,project,first.output_request_id)
        command=cmd(actor,project,first.output_request_id,first_facts.lock_version)
        before=state(db,args.port,first.output_request_id)
        for bad_command,bad_key,expected in [
            (cmd(actor,project,first.output_request_id,first_facts.lock_version-1),"p17-stale-version-000001","CONFLICT_VERSION"),
            (cmd(actor,other,first.output_request_id,first_facts.lock_version),"p17-cross-project-000001","RESOURCE_NOT_FOUND"),
        ]:
            try:owner.cancel(bad_command,idempotency_key=bad_key)
            except OutputRequestCancelError as exc:
                if exc.code!=expected:raise
            else:raise AssertionError(f"expected cancellation rejection {expected}")
            if state(db,args.port,first.output_request_id)!=before:
                raise AssertionError(f"{expected} rejection changed database rows")
        try:make_canceller(runtime,actor,allowed=False).cancel(
            command,idempotency_key="p17-denied-role-0000001")
        except OutputRequestCancelError as exc:
            if exc.code!="RESOURCE_NOT_FOUND":raise
        else:raise AssertionError("denied creator/manager policy authorized cancellation")
        if state(db,args.port,first.output_request_id)!=before:raise AssertionError("denied role changed rows")
        def issue(_):return owner.cancel(command,idempotency_key="p17-same-cancel-key-00001")
        with ThreadPoolExecutor(max_workers=2) as pool:pair=list(pool.map(issue,(1,2)))
        if any(x.state!="CANCELLED" for x in pair):raise AssertionError("same-key concurrent calls did not converge")
        after=state(db,args.port,first.output_request_id)
        if (after[0][1],after[0][2],after[0][3] is None,after[1][1],after[2],after[3]) != (
            "CANCELLED",first_facts.lock_version+1,False,"CANCELLED",1,1):
            raise AssertionError(f"pending cancel did not atomically persist expected facts: {after!r}")
        if after[0][3]>after[4]:raise AssertionError("Output completed_at is later than PostgreSQL clock")
        if (after[1][3],after[1][4],after[1][5] is None)!=(actor,command.reason,False):
            raise AssertionError("Job cancellation audit facts are incomplete")
        denied_request=create_request(create,project,"p17-denied-request-000001")
        denied_facts=get_facts(runtime,project,denied_request.output_request_id)
        denied_before=state(db,args.port,denied_request.output_request_id)
        try:make_canceller(runtime,actor,allowed=False).cancel(
            cmd(actor,project,denied_request.output_request_id,denied_facts.lock_version),
            idempotency_key="p17-denied-write-00000001")
        except OutputRequestCancelError as exc:
            if exc.code!="RESOURCE_NOT_FOUND":raise
        else:raise AssertionError("unauthorized role write succeeded")
        if state(db,args.port,denied_request.output_request_id)!=denied_before:
            raise AssertionError("unauthorized role left writes")
        bad=create_request(create,project,"p17-binding-source-0001")
        target=create_request(create,project,"p17-binding-target-0001")
        bad_facts=get_facts(runtime,project,bad.output_request_id)
        with runtime.unit_of_work() as tx:
            tx.session.execute(text("UPDATE plm.out_output_requests SET job_ref=:job WHERE output_request_id=:request"),
                {"job":target.job_id,"request":bad.output_request_id});tx.commit()
        bad_before=state(db,args.port,bad.output_request_id)
        try:owner.cancel(cmd(actor,project,bad.output_request_id,bad_facts.lock_version),
                         idempotency_key="p17-wrong-job-binding-001")
        except OutputRequestCancelError as exc:
            if exc.code!="RESOURCE_NOT_FOUND":raise
        else:raise AssertionError("OutputRequest linked to another Job was accepted")
        if state(db,args.port,bad.output_request_id)!=bad_before:raise AssertionError("wrong binding changed rows")
        failing=create_request(create,project,"p17-audit-source-00001")
        failing_facts=get_facts(runtime,project,failing.output_request_id)
        failing_before=state(db,args.port,failing.output_request_id)
        try:make_canceller(runtime,actor,audit=FailAudit()).cancel(
            cmd(actor,project,failing.output_request_id,failing_facts.lock_version),
            idempotency_key="p17-audit-failure-00001")
        except OutputRequestCancelError as exc:
            if exc.code!="SYSTEM_UNAVAILABLE":raise
        else:raise AssertionError("Audit failure did not abort cancellation")
        if state(db,args.port,failing.output_request_id)!=failing_before:
            raise AssertionError("Audit failure left Output/Job/receipt/Audit partial writes")
        running=create_request(create,project,"p17-running-source-00001")
        running_facts=get_facts(runtime,project,running.output_request_id)
        with runtime.unit_of_work() as tx:
            lease_until=tx.session.execute(text("SELECT clock_timestamp()+interval '5 minutes'")).scalar_one()
            tx.session.execute(text("UPDATE plm.job_jobs SET state='RUNNING',attempt_count=1,fencing_token=1,"
                "lease_expires_at=:until WHERE job_id=:job"),{"until":lease_until,"job":running.job_id})
            tx.session.add(JobLeaseRow(job_id=running.job_id,worker_ref="synthetic-output-worker",
                fencing_token=1,lease_expires_at=lease_until))
            tx.session.add(JobAttemptRow(job_id=running.job_id,attempt_no=1,
                worker_ref="synthetic-output-worker",fencing_token=1))
            tx.session.execute(text("UPDATE plm.out_output_requests SET request_state='GENERATING',"
                "lock_version=lock_version+1 WHERE output_request_id=:request"),
                {"request":running.output_request_id})
            tx.commit()
        running_facts=get_facts(runtime,project,running.output_request_id)
        running_result=owner.cancel(cmd(actor,project,running.output_request_id,running_facts.lock_version),
                                    idempotency_key="p17-running-cancel-key-0001")
        active=state(db,args.port,running.output_request_id)
        if (running_result.state,active[0][1],active[1][1],active[0][3]) != (
            "CANCEL_REQUESTED","CANCEL_REQUESTED","CANCEL_REQUESTED",None):
            raise AssertionError("RUNNING cancellation did not remain an unacknowledged request")
        result.update(status="PASS_SCOPE_LIMITED",pending_cancel_atomic=True,
            same_key_concurrency_one_audit_and_receipt=True,stale_if_match_no_writes=True,
            cross_project_no_writes=True,denied_role_no_writes=True,wrong_job_binding_no_writes=True,
            audit_failure_full_rollback=True,cancelled_at_database_clock=True,
            running_cancel_unacknowledged=True,customer_data=False,external_api_calls=0,
            product_api_started=False)
    finally:
        if runtime is not None:runtime.dispose()
        if created:drop_db(admin,db)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
