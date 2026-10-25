"""Real licensed-call boundary/Session/Project/Audit reads; License synthetic."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields,replace
from datetime import datetime,timezone,timedelta
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import uuid
import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.public import AuditService,AuditEventDraft
from plm_assistant.modules.audit.application.queries.audit_query import AuditSearch,AuditEventView
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditReadService,AuthorizedAuditReadError,AuditListQuery,AuditGetQuery
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.audit_read_repository import SqlAlchemyAuditReadRepository

spec=spec_from_file_location("_audit_read_fixture",Path(__file__).resolve().parents[1]/"rvw-02-a05-p02-authorized-start"/"verify.py")
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)
schema,auth=fixture.schema,fixture.auth


def main():
    name,runtime="auditread_"+uuid.uuid4().hex[:12],None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head")
            runtime=create_database_runtime(url)
            with schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(5)]
                users=[auth.user(db,f"Synthetic audit reader {i}",token,"DEPLOYMENT_ADMIN" if i==4 else "NONE") for i,token in enumerate(tokens)]
                projects=[schema.insert(db,"prj_projects",dict(project_code=f"AUD{i}",project_code_normalized=f"aud{i}",
                    name=f"Synthetic audit project {i}",created_by=users[0]),"project_id") for i in range(2)]
                department=schema.insert(db,"prj_departments",dict(project_id=projects[0],department_code="D",department_code_normalized="d",name="Synthetic department"),"department_id")
                for user,role in zip(users,("PROJECT_MANAGER","IMPLEMENTATION_MEMBER","CUSTOMER_MANAGER","CUSTOMER_MEMBER")):
                    schema.insert(db,"prj_project_members",dict(project_id=projects[0],user_id=user,department_id=department,project_role=role),"project_member_id")
                writer=AuditService(SqlAlchemyAuditRepository())
                def append(project=None,hint=False):
                    with runtime.unit_of_work() as tx:
                        event=AuditEventDraft(trace_id=uuid.uuid4(),event_scope="DEPLOYMENT" if project is None else "PROJECT",
                            target_project_id=project,actor_type="UNRESOLVED" if hint else "USER",actor_id=None if hint else users[0],
                            original_actor_id=None,actor_hint_digest=b"h"*32 if hint else None,action="SYNTHETIC_AUDIT_EVENT",outcome="SUCCESS")
                        result=writer.append(tx,event);tx.commit();return result
                local=[append(projects[0]) for _ in range(3)]
                foreign=append(projects[1])
                deployment=append(hint=True)
                guard=auth.Guard()
                deps=dict(unit_of_work=runtime.unit_of_work,project_access=SqlAlchemyProjectReadAccess(),deployment_access=SqlAlchemyDeploymentReadAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository()),
                    license_guard=guard,repository=SqlAlchemyAuditReadRepository())
                service=AuthorizedAuditReadService(**deps)
                now=datetime.now(timezone.utc)
                search=AuditSearch(now-timedelta(days=1),now+timedelta(days=1),page_size=2)
                q=AuditListQuery(tokens[0],projects[0],uuid.uuid4(),search)
                g=AuditGetQuery(tokens[0],projects[0],uuid.uuid4(),local[0])
                before=tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))
                first=service.list(q)
                second=service.list(replace(q,search=replace(search,after=first.next_position)))
                assert first.has_more and not second.has_more
                assert {v.audit_event_id for v in first.items+second.items}==set(local)
                assert len(first.items+second.items)==3
                assert service.get(g).audit_event_id==local[0]
                deployed=service.list(replace(q,session_token=tokens[4],project_id=None))
                assert [v.audit_event_id for v in deployed.items]==[deployment]
                assert "actor_hint_digest" not in {f.name for f in fields(AuditEventView)}
                assert all(v.event_scope=="DEPLOYMENT" and v.target_project_id is None for v in deployed.items)
                def deny(query,code):
                    try:service.get(query) if type(query) is AuditGetQuery else service.list(query)
                    except AuthorizedAuditReadError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("unauthorized audit read accepted")
                for token in tokens[1:]:deny(replace(q,session_token=token),"RESOURCE_NOT_FOUND")
                for token in tokens[:4]:deny(replace(q,session_token=token,project_id=None),"AUTH_ACCESS_DENIED")
                deny(replace(q,project_id=projects[1]),"RESOURCE_NOT_FOUND")
                deny(replace(g,event_id=foreign),"RESOURCE_NOT_FOUND")
                deny(replace(g,event_id=deployment),"RESOURCE_NOT_FOUND")
                deny(replace(g,session_token=tokens[4],project_id=None),"RESOURCE_NOT_FOUND")
                guard.enabled=False;deny(q,"LICENSE_OPERATION_DENIED");deny(replace(q,session_token=tokens[4],project_id=None),"LICENSE_OPERATION_DENIED");guard.enabled=True
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))==before

                class LockProbeRepository(SqlAlchemyAuditReadRepository):
                    def get_event(self,tx,**kw):
                        result=super().get_event(tx,**kw)
                        checks=(("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",users[0]),
                            ("SELECT 1 FROM plm.auth_sessions WHERE user_id=%s FOR UPDATE",users[0]),
                            ("SELECT 1 FROM plm.prj_projects WHERE project_id=%s FOR UPDATE",projects[0]),
                            ("SELECT 1 FROM plm.prj_project_members WHERE user_id=%s FOR UPDATE",users[0]),
                            ("SELECT 1 FROM plm.prj_departments WHERE department_id=%s FOR UPDATE",department))
                        def competitor(check):
                            with schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='150ms'")
                                try:
                                    with rival.transaction():rival.execute(check[0],(check[1],))
                                except psycopg.errors.LockNotAvailable:return "locked"
                                raise AssertionError("current audit authority fact escaped UOW")
                        with ThreadPoolExecutor(max_workers=1) as pool:assert list(pool.map(competitor,checks))==["locked"]*5
                        return result
                assert AuthorizedAuditReadService(**(deps|dict(repository=LockProbeRepository()))).get(g).audit_event_id==local[0]
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(projects[0],))
                assert service.get(g).audit_event_id==local[0]  # read history, no new writes
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(q,"RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(q,"AUTH_ACCESS_DENIED")
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))==before
            print("AUD-02-A01 PASS: real Session/PM/Admin/current scope/detail/keyset, no Admin project bypass, revoked/archive behavior, five fact locks, safe projection/no writes; synthetic License, no HTTP/export/production")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
