"""Real current User/Project facts for async stages; coordinates and License synthetic."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.auth.infrastructure.current_user_access import SqlAlchemyCurrentUserAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.export_contract import AuditExportAuthorityRequest
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthority, AuditExportCurrentAuthorityError

load=spec_from_file_location("_current_export_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="auditcurrent_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            with f.schema.connect(name) as db:
                users=[f.auth.user(db,f"Synthetic current export {i}",bytes([i+1])*32,"DEPLOYMENT_ADMIN" if i==4 else "NONE") for i in range(5)]
                projects=[f.schema.insert(db,"prj_projects",dict(project_code=f"CURRENT{i}",project_code_normalized=f"current{i}",name=f"Synthetic current project {i}",created_by=users[0]),"project_id") for i in range(2)]
                dept=f.schema.insert(db,"prj_departments",dict(project_id=projects[0],department_code="D",department_code_normalized="d",name="Synthetic current department"),"department_id")
                for user,role in zip(users,("PROJECT_MANAGER","IMPLEMENTATION_MEMBER","CUSTOMER_MANAGER","CUSTOMER_MEMBER")):
                    f.schema.insert(db,"prj_project_members",dict(project_id=projects[0],user_id=user,department_id=dept,project_role=role),"project_member_id")
                guard=f.auth.Guard()
                service=AuditExportCurrentAuthority(users=SqlAlchemyCurrentUserAccess(),projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository()),license_guard=guard)
                req=AuditExportAuthorityRequest(uuid4(),users[0],"PROJECT",projects[0],"CAPTURE")
                deployed=replace(req,actor_id=users[4],scope="DEPLOYMENT",project_id=None)
                def authorize(request):
                    with runtime.unit_of_work() as tx:assert service.assert_current(tx,request=request) is None
                def deny(request,code):
                    try:authorize(request)
                    except AuditExportCurrentAuthorityError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("current authority improperly granted")
                watched=("aud_exports","aud_export_acceptances","aud_export_members","aud_export_captures","job_jobs","job_leases","job_attempts","job_outbox_events","plt_idempotency_receipts","aud_events")
                def snapshot():return {table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in watched}
                before=snapshot()
                for stage in ("CAPTURE","RENDER","PUBLISH"):
                    authorize(replace(req,stage=stage));authorize(replace(deployed,stage=stage))
                    for user in users[1:]:deny(replace(req,actor_id=user,stage=stage),"RESOURCE_NOT_FOUND")
                    for user in users[:4]:deny(replace(deployed,actor_id=user,stage=stage),"AUTH_ACCESS_DENIED")
                    deny(replace(req,project_id=projects[1],stage=stage),"RESOURCE_NOT_FOUND")
                deny(replace(req,actor_id=uuid4()),"AUTH_ACCESS_DENIED")
                # Async work does not require or persist an original Session. HTTP still does.
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1")
                authorize(req);authorize(deployed)
                checks=(("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",users[0]),
                        ("SELECT 1 FROM plm.prj_projects WHERE project_id=%s FOR UPDATE",projects[0]),
                        ("SELECT 1 FROM plm.prj_project_members WHERE user_id=%s FOR UPDATE",users[0]),
                        ("SELECT 1 FROM plm.prj_departments WHERE department_id=%s FOR UPDATE",dept))
                def competitor(check):
                    with f.schema.connect(name) as rival:
                        rival.execute("SET lock_timeout='100ms'")
                        try:
                            with rival.transaction():rival.execute(check[0],(check[1],))
                        except psycopg.errors.LockNotAvailable:return True
                        return False
                with runtime.unit_of_work() as tx:
                    service.assert_current(tx,request=req)
                    with ThreadPoolExecutor(max_workers=1) as pool:assert all(pool.map(competitor,checks))
                with runtime.unit_of_work() as tx:
                    service.assert_current(tx,request=deployed)
                    with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(competitor,checks[0][:1]+(users[4],)).result()
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(projects[0],))
                authorize(req)
                mutations=(
                    ("prj_project_members","state","SUSPENDED","ACTIVE","user_id",users[0],req,"RESOURCE_NOT_FOUND"),
                    ("prj_project_members","project_role","IMPLEMENTATION_MEMBER","PROJECT_MANAGER","user_id",users[0],req,"RESOURCE_NOT_FOUND"),
                    ("prj_departments","state","INACTIVE","ACTIVE","department_id",dept,req,"RESOURCE_NOT_FOUND"),
                    ("auth_users","state","DISABLED","ENABLED","user_id",users[0],req,"AUTH_ACCESS_DENIED"),
                    ("auth_users","deployment_role","NONE","DEPLOYMENT_ADMIN","user_id",users[4],deployed,"AUTH_ACCESS_DENIED"))
                for table,column,bad,good,key,identity,request,code in mutations:
                    query=sql.SQL("UPDATE plm.{} SET {}=%s,lock_version=lock_version+1 WHERE {}=%s").format(sql.Identifier(table),sql.Identifier(column),sql.Identifier(key))
                    db.execute(query,(bad,identity))
                    for stage in ("CAPTURE","RENDER","PUBLISH"):deny(replace(request,stage=stage),code)
                    db.execute(query,(good,identity));authorize(request)
                guard.enabled=False
                for request in (req,deployed):
                    for stage in ("CAPTURE","RENDER","PUBLISH"):deny(replace(request,stage=stage),"LICENSE_OPERATION_DENIED")
                assert snapshot()==before
            print("AUD-03-A06-A01 PASS: actual enabled User/admin/PM/member/department at every stage; real four-fact and deployment locks held until caller exits; archived maintenance/no admin project bypass/cross-project/retracted facts/synthetic License deny; Session revocation not async cancellation; no business writes. Export coordinates synthetic, NOT accepted Root binding/Job Lease/capture/publish/HTTP/production License")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
