"""Hosted PostgreSQL 18 HTTP composition checks for OutputRequest cancellation."""
from __future__ import annotations
import argparse,asyncio,hashlib,json,re,sys,uuid
from pathlib import Path
import psycopg
from sqlalchemy import URL,text
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps"/"backend"/"src"))
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.output_cancel import OutputJobCancellation
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobQueue
from plm_assistant.modules.jobs.infrastructure.output_cancel_repository import SqlAlchemyOutputJobCancellationRepository
from plm_assistant.modules.jobs.infrastructure.output_enqueue_repository import SqlAlchemyOutputJobQueueRepository
from plm_assistant.modules.output.api.cancel_request import create_output_request_cancel_router
from plm_assistant.modules.output.application.cancel_request import (
    OutputRequestCancelService,OutputRequestCancelError)
from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest,OutputRequestService,ResolvedOutputContext)
from plm_assistant.modules.output.infrastructure.cancel_access import SqlAlchemyOutputRequestCancelAccess
from plm_assistant.modules.output.infrastructure.cancel_request_repository import SqlAlchemyOutputRequestCancelRepository
from plm_assistant.modules.output.infrastructure.create_request_repository import SqlAlchemyOutputRequestRepository
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow,ProjectMemberRow,ProjectRow)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository

TOKEN=b"t"*32
CSRF=b"c"*32
class CreateAccess:
    def __init__(self,actor):self.actor=actor
    def authorized_creator(self,*_,**__):return self.actor
class SyntheticSessionAccess:
    def __init__(self,actor):self.actor=actor
    def authenticated_user(self,transaction,*,session_token,csrf_token,now):
        if session_token!=TOKEN or csrf_token!=CSRF:return None
        return self.actor
class SyntheticSessions:
    def validate(self,token,*,csrf_token=None,require_csrf=False):
        if token!=TOKEN or csrf_token!=CSRF or require_csrf is not True:
            raise RuntimeError("synthetic session rejected")
class SyntheticOrigins:
    def require_trusted(self,headers):
        if not any(n.lower()==b"origin" and v==b"http://localhost" for n,v in headers):
            raise RuntimeError("synthetic origin rejected")
class SyntheticLicense:
    def require_valid(self,**_):return True
class Resolver:
    def resolve(self,transaction,*,actor_id,command):
        payload={"source_order":[str(v) for v in command.source_version_refs],"synthetic":True}
        return ResolvedOutputContext(command.source_version_refs,payload,canonical_payload_fingerprint(payload))
def url(name,port):return URL.create("postgresql+psycopg",username="postgres",host="127.0.0.1",port=port,database=name)
def dsn(name,port):return f"postgresql://postgres@127.0.0.1:{port}/{name}"
def create_db(admin,name):
    with psycopg.connect(admin,autocommit=True) as c:c.execute(f'CREATE DATABASE "{name}" TEMPLATE postgres')
def drop_db(admin,name):
    with psycopg.connect(admin,autocommit=True) as c:c.execute(f'DROP DATABASE IF EXISTS "{name}"')
def create_owner(runtime,actor):
    return OutputRequestService(unit_of_work=runtime.unit_of_work,access=CreateAccess(actor),
        license_guard=SyntheticLicense(),resolver=Resolver(),
        repository=SqlAlchemyOutputRequestRepository(),
        jobs=OutputJobQueue(SqlAlchemyOutputJobQueueRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(),
        audit=AuditService(SqlAlchemyAuditRepository()))
def make_request(owner,project,key):
    src,template,trace=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    command=CreateOutputRequest(b"1"*32,b"2"*32,trace,project,"DOCX",template,(src,),
        "standard-output.v1","word.generate")
    return owner.create(command,idempotency_key=key)
def get_cancel_facts(runtime,project,request):
    with runtime.unit_of_work() as tx:
        return SqlAlchemyOutputRequestCancelRepository().get_for_update(
            tx,project_id=project,output_request_id=request)
def request_app(runtime,actor):
    authorization=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    access=SqlAlchemyOutputRequestCancelAccess(
        authorization=authorization,session_access=SyntheticSessionAccess(actor))
    service=OutputRequestCancelService(unit_of_work=runtime.unit_of_work,access=access,
        license_guard=SyntheticLicense(),repository=SqlAlchemyOutputRequestCancelRepository(),
        jobs=OutputJobCancellation(SqlAlchemyOutputJobCancellationRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(),audit=AuditService(SqlAlchemyAuditRepository()))
    router=create_output_request_cancel_router(
        sessions=SyntheticSessions(),origins=SyntheticOrigins(),service=service)
    return create_app(output_request_cancel_router=router)
async def asgi_post(app,path,headers,body):
    messages=[];sent=False
    async def receive():
        nonlocal sent
        if not sent:
            sent=True
            return {"type":"http.request","body":body,"more_body":False}
        return {"type":"http.disconnect"}
    async def send(message):messages.append(message)
    scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.3"},
        "http_version":"1.1","method":"POST","scheme":"http","path":path,
        "raw_path":path.encode("ascii"),"query_string":b"","headers":headers,
        "client":("127.0.0.1",43000),"server":("localhost",80)}
    await app(scope,receive,send)
    start=next(m for m in messages if m["type"]=="http.response.start")
    payload=b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
    return start["status"],json.loads(payload)
def post_cancel(runtime,actor,project,request_id,version,key):
    app=request_app(runtime,actor)
    path=f"/api/v1/projects/{project}/output-requests/{request_id}:cancel"
    headers=((b"origin",b"http://localhost"),
        (b"cookie",b"plm_session="+TOKEN.hex().encode("ascii")),
        (b"x-csrf-token",CSRF.hex().encode("ascii")),
        (b"idempotency-key",key.encode("ascii")),
        (b"if-match",f'"v{version}"'.encode("ascii")),
        (b"content-type",b"application/json"))
    return asyncio.run(asgi_post(app,path,headers,b'{"reason":"synthetic HTTP cancellation"}'))
def persisted(database,port,request):
    with psycopg.connect(dsn(database,port)) as c:
        output=c.execute("SELECT request_state,lock_version,completed_at,job_ref FROM plm.out_output_requests WHERE output_request_id=%s",(request,)).fetchone()
        job=c.execute("SELECT state,lock_version FROM plm.job_jobs WHERE job_id=%s",(output[3],)).fetchone()
        audit=c.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='OUTPUT_REQUEST_CANCEL'",(request,)).fetchone()[0]
        receipt=c.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_OUTPUT_REQUEST_CANCEL' AND result_ref_id=%s",(request,)).fetchone()[0]
        return output[:3],job,audit,receipt
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--port",type=int,required=True)
    parser.add_argument("--run-id",required=True);args=parser.parse_args()
    if not 1<=args.port<=65535 or not re.fullmatch(r"[0-9]{1,12}",args.run_id):
        raise ValueError("temporary loopback PG and numeric hosted run ID required")
    db="plm_out18_"+args.run_id[-10:];admin=dsn("postgres",args.port);created=False;runtime=None
    result={"status":"PENDING","customer_data":False,"external_api_calls":0,
        "database":"isolated synthetic PostgreSQL 18.6","product_api_started":False}
    try:
        create_db(admin,db);created=True;upgrade_database(url(db,args.port),"head")
        runtime=create_database_runtime(url(db,args.port))
        creator,manager,implementer,project=[uuid.uuid4() for _ in range(4)]
        department=uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=creator,username_display="p18-synthetic-creator",
                    username_normalized="p18-synthetic-creator",state="DISABLED",deployment_role="NONE"),
                UserRow(user_id=manager,username_display="p18-synthetic-manager",
                    username_normalized="p18-synthetic-manager",state="DISABLED",deployment_role="NONE"),
                UserRow(user_id=implementer,username_display="p18-synthetic-implementer",
                    username_normalized="p18-synthetic-implementer",state="DISABLED",deployment_role="NONE"),
                ProjectRow(project_id=project,project_code="P18-A",project_code_normalized="P18-A",
                    name="Synthetic Output Cancel HTTP",created_by=creator),
                DepartmentRow(department_id=department,project_id=project,
                    department_code="P18",department_code_normalized="P18",
                    name="Synthetic P18 Department",state="ACTIVE"),
                ProjectMemberRow(project_member_id=uuid.uuid4(),project_id=project,
                    user_id=manager,department_id=department,project_role="PROJECT_MANAGER",
                    state="ACTIVE"),
                ProjectMemberRow(project_member_id=uuid.uuid4(),project_id=project,
                    user_id=implementer,department_id=department,project_role="IMPLEMENTATION_MEMBER",
                    state="ACTIVE")])
            tx.commit()
        owner=create_owner(runtime,creator)
        manager_request=make_request(owner,project,"p18-manager-cancel-00001")
        manager_facts=get_cancel_facts(runtime,project,manager_request.output_request_id)
        manager_status,manager_body=post_cancel(runtime,manager,project,
            manager_request.output_request_id,manager_facts.lock_version,"p18-manager-http-0001")
        if manager_status!=200 or manager_body["data"]["state"]!="CANCELLED":
            raise AssertionError("ProjectManager HTTP cancellation did not succeed")
        manager_rows=persisted(db,args.port,manager_request.output_request_id)
        if manager_rows[0][0]!="CANCELLED" or manager_rows[1][0]!="CANCELLED" or manager_rows[2:]!=(1,1):
            raise AssertionError("ProjectManager HTTP cancellation did not persist atomic audit/idempotency")
        creator_request=make_request(owner,project,"p18-creator-cancel-00001")
        creator_facts=get_cancel_facts(runtime,project,creator_request.output_request_id)
        creator_status,creator_body=post_cancel(runtime,creator,project,
            creator_request.output_request_id,creator_facts.lock_version,"p18-creator-http-0001")
        if creator_status!=200 or creator_body["data"]["state"]!="CANCELLED":
            raise AssertionError("creator HTTP cancellation did not succeed")
        denied_request=make_request(owner,project,"p18-implementation-cancel-01")
        denied_facts=get_cancel_facts(runtime,project,denied_request.output_request_id)
        before=persisted(db,args.port,denied_request.output_request_id)
        denied_status,_=post_cancel(runtime,implementer,project,
            denied_request.output_request_id,denied_facts.lock_version,"p18-implementation-http-01")
        if denied_status!=404:
            raise AssertionError("ImplementationMember unexpectedly received cancel permission")
        if persisted(db,args.port,denied_request.output_request_id)!=before:
            raise AssertionError("ImplementationMember HTTP rejection wrote persistent rows")
        default=create_app()
        cancel_path="/api/v1/projects/{project_id}/output-requests/{output_request_id}:cancel"
        if any(getattr(route,"path","")==cancel_path for route in default.routes):
            raise AssertionError("default app unexpectedly mounted Output cancellation")
        result.update(status="PASS_SCOPE_LIMITED",
            creator_http_cancel_allowed=True,project_manager_http_cancel_allowed=True,
            implementation_member_http_cancel_denied_no_writes=True,
            default_app_cancel_route_absent=True,customer_data=False,external_api_calls=0)
    finally:
        if runtime is not None:runtime.dispose()
        if created:drop_db(admin,db)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
