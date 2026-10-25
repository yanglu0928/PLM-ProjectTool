"""Real submit Session/CSRF/current project/admin facts; synthetic License."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService,ProjectAuthorizationError
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.export_submit_authorization import (
    AuditExportSubmitAuthorization,AuditExportSubmitAuthorizationRequest,AuditExportSubmitAuthorizationError,
)

load=spec_from_file_location("_audit_submit_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="auditsubmitauth_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            with f.schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(5)]
                users=[f.auth.user(db,f"Synthetic export submit {i}",token,"DEPLOYMENT_ADMIN" if i==4 else "NONE") for i,token in enumerate(tokens)]
                projects=[f.schema.insert(db,"prj_projects",dict(project_code=f"SUBMIT{i}",project_code_normalized=f"submit{i}",name=f"Synthetic export submit project {i}",created_by=users[0]),"project_id") for i in range(2)]
                department=f.schema.insert(db,"prj_departments",dict(project_id=projects[0],department_code="D",department_code_normalized="d",name="Synthetic submit department"),"department_id")
                for user,role in zip(users,("PROJECT_MANAGER","IMPLEMENTATION_MEMBER","CUSTOMER_MANAGER","CUSTOMER_MEMBER")):
                    f.schema.insert(db,"prj_project_members",dict(project_id=projects[0],user_id=user,department_id=department,project_role=role),"project_member_id")
                guard=f.auth.Guard()
                projects_service=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository())
                deps=dict(project_access=SqlAlchemyProjectWriteAccess(),deployment_access=SqlAlchemyLicenseImportAccess(),projects=projects_service,license_guard=guard)
                service=AuditExportSubmitAuthorization(**deps)
                now=datetime.now(timezone.utc)
                spec=AuditExportSpec("PROJECT",projects[0],"PROJECT_GOVERNANCE",now-timedelta(days=1),now)
                request=AuditExportSubmitAuthorizationRequest(tokens[0],f.auth.CSRF,uuid4(),spec)
                deployed=replace(request,session_token=tokens[4],spec=replace(spec,scope="DEPLOYMENT",project_id=None,purpose="SECURITY_REVIEW"))
                def authorize(req,svc=service):
                    with runtime.unit_of_work() as tx:return svc.require_in_transaction(tx,request=req)
                def deny(req,code,svc=service):
                    try:authorize(req,svc)
                    except AuditExportSubmitAuthorizationError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("unauthorized export submit accepted")
                watched=("aud_exports","aud_export_members","aud_export_captures","job_jobs","job_outbox_events","plt_idempotency_receipts","aud_events")
                before={table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in watched}
                result=authorize(request)
                assert result.actor_id==users[0] and result.project_id==projects[0] and result.intent_hash==spec.fingerprint()
                assert authorize(deployed).actor_id==users[4]
                for token in tokens[1:]:deny(replace(request,session_token=token),"RESOURCE_NOT_FOUND")
                for token in tokens[:4]:deny(replace(deployed,session_token=token),"AUTH_ACCESS_DENIED")
                deny(replace(request,spec=replace(spec,project_id=projects[1])),"RESOURCE_NOT_FOUND")
                other_department=f.schema.insert(db,"prj_departments",dict(project_id=projects[1],department_code="D",department_code_normalized="d",name="Synthetic explicit admin membership"),"department_id")
                f.schema.insert(db,"prj_project_members",dict(project_id=projects[1],user_id=users[4],department_id=other_department,project_role="PROJECT_MANAGER"),"project_member_id")
                explicit_admin=replace(request,session_token=tokens[4],spec=replace(spec,project_id=projects[1]))
                assert authorize(explicit_admin).actor_id==users[4]
                deny(replace(request,session_token=tokens[4]),"RESOURCE_NOT_FOUND")
                for req in (request,deployed):
                    deny(replace(req,csrf_token=b"z"*32),"AUTH_ACCESS_DENIED")
                    deny(replace(req,session_token=b"z"*32),"AUTH_ACCESS_DENIED")
                guard.enabled=False
                deny(request,"LICENSE_OPERATION_DENIED");deny(deployed,"LICENSE_OPERATION_DENIED");guard.enabled=True
                future=AuditExportSubmitAuthorization(**deps,clock=lambda:now+timedelta(days=400))
                deny(request,"AUTH_ACCESS_DENIED",future);deny(deployed,"AUTH_ACCESS_DENIED",future)
                # Both auth and project facts remain locked AFTER service returns until caller ends UOW.
                checks=(("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",users[0]),
                    ("SELECT 1 FROM plm.auth_sessions WHERE user_id=%s FOR UPDATE",users[0]),
                    ("SELECT 1 FROM plm.prj_projects WHERE project_id=%s FOR UPDATE",projects[0]),
                    ("SELECT 1 FROM plm.prj_project_members WHERE user_id=%s FOR UPDATE",users[0]),
                    ("SELECT 1 FROM plm.prj_departments WHERE department_id=%s FOR UPDATE",department))
                def competitor(check):
                    with f.schema.connect(name) as rival:
                        rival.execute("SET lock_timeout='100ms'")
                        try:
                            with rival.transaction():rival.execute(check[0],(check[1],))
                        except psycopg.errors.LockNotAvailable:return True
                        return False
                with runtime.unit_of_work() as tx:
                    service.require_in_transaction(tx,request=request)
                    with ThreadPoolExecutor(max_workers=1) as pool:assert all(pool.map(competitor,checks))
                # Archive does not grant general business write/Job access.
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(projects[0],))
                assert authorize(request)==result
                with runtime.unit_of_work() as tx:
                    try:projects_service.require_in_transaction(tx,user_id=users[0],project_id=projects[0],operation="WORKFLOW_START")
                    except ProjectAuthorizationError as exc:assert exc.code=="PROJECT_ARCHIVED"
                    else:raise AssertionError("export maintenance opened ordinary archived write")
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(request,"RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                db.execute("UPDATE plm.prj_departments SET state='INACTIVE',lock_version=lock_version+1 WHERE department_id=%s",(department,))
                deny(request,"RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.prj_departments SET state='ACTIVE',lock_version=lock_version+1 WHERE department_id=%s",(department,))
                db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(request,"RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(request,"AUTH_ACCESS_DENIED")
                db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",(users[4],))
                deny(deployed,"AUTH_ACCESS_DENIED")
                db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(users[4],))
                assert authorize(deployed).actor_id==users[4]
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(request,"AUTH_ACCESS_DENIED")
                for table in watched:
                    assert tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table))))==before[table]
            print("AUD-03-A05-A01 PASS: real submit Session/CSRF/PM/Admin/current membership/department/role locks; no Admin project bypass; archived export only; expiry/revocation/disabled/retracted role/CSRF and synthetic License deny; five facts held until caller UOW ends; no Export/Job/receipt/Audit writes. NOT Worker authority/queue/HTTP/production License")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
