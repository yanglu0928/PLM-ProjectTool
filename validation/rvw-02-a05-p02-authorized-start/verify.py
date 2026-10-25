"""Real Session/CSRF/Project/qualification/start/Audit/receipt; synthetic Subject/License."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Event
import uuid
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.review.application.start_round import ReviewStartService,StartReviewRound,ReviewStartError
from plm_assistant.modules.review.application.subject_start import PreparedReviewSubject,ReviewSubjectAccessDenied
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository

spec=spec_from_file_location("_authorized_start_fixture",Path(__file__).resolve().parents[1]/"rvw-01-a05-authorized-read"/"verify.py")
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)
schema,auth=fixture.schema,fixture.auth


def main():
    name,runtime="rvwstart_"+uuid.uuid4().hex[:12],None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head")
            runtime=create_database_runtime(url)
            with schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(5)]
                users=[auth.user(db,f"Synthetic start {i}",token,"DEPLOYMENT_ADMIN" if i==4 else "NONE") for i,token in enumerate(tokens)]
                project=schema.insert(db,"prj_projects",dict(project_code="RS",project_code_normalized="rs",name="Synthetic start",created_by=users[0]),"project_id")
                department=schema.insert(db,"prj_departments",dict(project_id=project,department_code="D",department_code_normalized="d",name="Synthetic department"),"department_id")
                for user,role in zip(users,("PROJECT_MANAGER","IMPLEMENTATION_MEMBER","CUSTOMER_MANAGER","CUSTOMER_MEMBER")):
                    schema.insert(db,"prj_project_members",dict(project_id=project,user_id=user,department_id=department,project_role=role),"project_member_id")
                reviews=[schema.review(db,users[0],project) for _ in range(6)]
                class SyntheticOwner:
                    """TEST ONLY data/check injector, not a real business identity lock."""
                    deny=False
                    def prepare_start_in_transaction(self,tx,r):
                        if self.deny:raise ReviewSubjectAccessDenied()
                        return PreparedReviewSubject(r,b"s"*32,1,datetime.now(timezone.utc),r.reviewer_ids,())
                    def assert_active_lock_in_transaction(self,tx,r):return None
                    def require_start_replay_access_in_transaction(self,tx,**k):
                        if self.deny:raise ReviewSubjectAccessDenied()
                owner,guard=SyntheticOwner(),auth.Guard()
                projectrepo=SqlAlchemyProjectAuthorizationRepository()
                deps=dict(unit_of_work=runtime.unit_of_work,access=SqlAlchemyReviewStartAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=projectrepo),
                    reviewers=ProjectReviewerQualificationService(users=SqlAlchemyReviewUserAccess(),projects=projectrepo),
                    license_guard=guard,repository=SqlAlchemyReviewStartRepository(),receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),subjects=owner)
                service=ReviewStartService(**deps)
                cmd=StartReviewRound(tokens[0],auth.CSRF,project,reviews[0],uuid.uuid4(),tuple(users[2:4]),"SYNTHETIC_ALL_V1",0,uuid.uuid4())
                def start(c=cmd,key="synthetic-authorized-start",use=service):return use.start_idempotent(c,idempotency_key=key)
                def deny(c,code,key="synthetic-authorized-start",use=service):
                    try:start(c,key,use)
                    except ReviewStartError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("unauthorized Review start accepted")
                def snapshot():return schema.snapshot(db),tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")),tuple(db.execute("SELECT * FROM plm.plt_idempotency_receipts ORDER BY receipt_id"))
                before=snapshot()
                for token in tokens[1:]:deny(replace(cmd,session_token=token),"RESOURCE_NOT_FOUND")
                deny(replace(cmd,session_token=tokens[1],reviewer_ids=(uuid.uuid4(),)),"RESOURCE_NOT_FOUND")
                deny(replace(cmd,csrf_token=b"x"*32),"AUTH_ACCESS_DENIED")
                deny(replace(cmd,project_id=uuid.uuid4()),"RESOURCE_NOT_FOUND")
                deny(replace(cmd,reviewer_ids=(users[4],)),"REVIEW_REVIEWER_INELIGIBLE")
                deny(replace(cmd,expected_version=1),"CONFLICT_VERSION")
                deny(cmd,"RESOURCE_NOT_FOUND",use=ReviewStartService(**(deps|dict(subjects=None))))
                guard.enabled=False;deny(cmd,"LICENSE_OPERATION_DENIED");guard.enabled=True
                assert snapshot()==before
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:start(),range(2)))
                result=results[0]
                assert result==results[1]==start(replace(cmd,reviewer_ids=tuple(reversed(cmd.reviewer_ids))))
                assert db.execute("SELECT count(*) FROM plm.rvw_review_rounds").fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_STARTED'").fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE state='COMPLETED'").fetchone()[0]==1
                before=snapshot()
                deny(replace(cmd,subject_version_id=uuid.uuid4()),"CONFLICT_IDEMPOTENCY")
                owner.deny=True;deny(cmd,"RESOURCE_NOT_FOUND");owner.deny=False
                deny(replace(cmd,expected_version=1),"REVIEW_SUBJECT_LOCKED",key="synthetic-other-start-key")
                assert snapshot()==before
                with db.transaction():
                    schema.decide(db,result.round_id,users[2]);schema.decide(db,result.round_id,users[3])
                db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[2],))
                assert start()==result  # old complete receipt, not another approval
                fresh=replace(cmd,review_id=reviews[1])
                deny(fresh,"REVIEW_REVIEWER_INELIGIBLE",key="synthetic-fresh-start")
                db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[2],))
                before=snapshot()
                deny(fresh,"REVIEW_UNAVAILABLE",key="synthetic-failed-audit",use=ReviewStartService(**(deps|dict(audit=auth.FailedAudit()))))
                class FailedReceipt(SqlAlchemyIdempotencyReceipts):
                    def complete(self,*a,**k):super().complete(*a,**k);raise RuntimeError("synthetic receipt failure")
                deny(fresh,"REVIEW_UNAVAILABLE",key="synthetic-failed-receipt",use=ReviewStartService(**(deps|dict(receipts=FailedReceipt()))))
                assert snapshot()==before
                # Force a REAL PostgreSQL 40P01 with a legacy reverse User lock
                # sequence. Start must rollback the entire first UOW then retry.
                authenticated,competitor_locked=Event(),Event()
                class DeadlockAccess(SqlAlchemyReviewStartAccess):
                    calls=0
                    def authenticated_user(self,tx,**k):
                        self.calls+=1
                        tx.session.execute(text("SET LOCAL deadlock_timeout='50ms'"))
                        actor=super().authenticated_user(tx,**k)
                        if self.calls==1:
                            authenticated.set();assert competitor_locked.wait(timeout=10)
                        return actor
                access=DeadlockAccess()
                def competitor():
                    assert authenticated.wait(timeout=10)
                    with schema.connect(name) as rival,rival.transaction():
                        rival.execute("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",(users[2],))
                        competitor_locked.set()
                        rival.execute("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",(users[0],))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    competing=pool.submit(competitor)
                    recovered=start(replace(cmd,review_id=reviews[2]),"synthetic-real-deadlock",ReviewStartService(**(deps|dict(access=access))))
                    competing.result(timeout=10)
                assert access.calls==2
                assert db.execute("SELECT count(*) FROM plm.rvw_review_rounds WHERE review_id=%s",(reviews[2],)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='REVIEW_STARTED'",(recovered.round_id,)).fetchone()[0]==1
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(project,))
                deny(cmd,"PROJECT_ARCHIVED")
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(cmd,"AUTH_ACCESS_DENIED")
            print("RVW-02-A05-P02 PASS: real Session/CSRF/PM/qualification/round/Audit/receipt, concurrent immutable replay/history, permission/License denial, full rollback, REAL 40P01 whole-tx recovery once; synthetic Subject/License, no HTTP/Gate")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
