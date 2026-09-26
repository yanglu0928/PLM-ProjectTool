"""Real Session/Project/owned commands/Audit/receipts; TEST ONLY Owner/License."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Event
import uuid
from alembic import command
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.review.application.transition_command import (
    ReviewTransitionCommandService,ReviewTransitionCommandError,DecideReviewRound,WithdrawReviewRound,
)
from plm_assistant.modules.review.application.subject_start import ReviewSubjectAccessDenied
from plm_assistant.modules.review.infrastructure.transition_repository import SqlAlchemyReviewTransitionRepository
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind

spec=spec_from_file_location("_authorized_transition_fixture",Path(__file__).resolve().parents[1]/"rvw-02-a05-p02-authorized-start"/"verify.py")
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)
schema,auth=fixture.schema,fixture.auth


def main():
    name,runtime="reviewcommand_"+uuid.uuid4().hex[:12],None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head")
            runtime=create_database_runtime(url)
            with schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(5)]
                users=[auth.user(db,f"Synthetic command {i}",token,"DEPLOYMENT_ADMIN" if i==4 else "NONE") for i,token in enumerate(tokens)]
                project=schema.insert(db,"prj_projects",dict(project_code="RC",project_code_normalized="rc",name="Synthetic commands",created_by=users[0]),"project_id")
                department=schema.insert(db,"prj_departments",dict(project_id=project,department_code="D",department_code_normalized="d",name="Synthetic department"),"department_id")
                for user,role in zip(users,("PROJECT_MANAGER","IMPLEMENTATION_MEMBER","CUSTOMER_MANAGER","CUSTOMER_MEMBER")):
                    schema.insert(db,"prj_project_members",dict(project_id=project,user_id=user,department_id=department,project_role=role),"project_member_id")
                db.execute("CREATE TABLE public.synthetic_owner_consumption(round_id uuid PRIMARY KEY,consumed integer NOT NULL DEFAULT 0,result_state text)")
                def seed(reviewers=tuple(users[2:4])):
                    review=schema.review(db,users[0],project)
                    with db.transaction():
                        round_id,_,_=schema.start(db,review,users[0],reviewers)
                        db.execute("INSERT INTO public.synthetic_owner_consumption(round_id) VALUES(%s)",(round_id,))
                    return review,round_id
                pairs=[seed() for _ in range(6)]
                recovery=seed((users[2],))
                allroles=seed(tuple(users[:4]))
                class SyntheticOwner:
                    """TEST ONLY marker/failure injection, NOT actual Subject qualification/lock."""
                    deny_replay=False
                    fail_consume=False
                    def require_transition_access_in_transaction(self,tx,intent):pass
                    def assert_transition_lock_in_transaction(self,tx,intent):
                        assert tx.session.execute(text("SELECT consumed FROM public.synthetic_owner_consumption WHERE round_id=:id FOR UPDATE"),dict(id=intent.after_progress.round_id)).scalar_one()==0
                    def consume_terminal_in_transaction(self,tx,intent):
                        tx.session.execute(text("UPDATE public.synthetic_owner_consumption SET consumed=consumed+1,result_state=:s WHERE round_id=:id"),dict(id=intent.after_progress.round_id,s=intent.after_progress.state.value))
                        if self.fail_consume:raise RuntimeError("synthetic consume failure after write")
                    def assert_terminal_consumed_in_transaction(self,tx,intent):
                        assert tuple(tx.session.execute(text("SELECT consumed,result_state FROM public.synthetic_owner_consumption WHERE round_id=:id"),dict(id=intent.after_progress.round_id)).one())==(1,intent.after_progress.state.value)
                    def require_transition_replay_access_in_transaction(self,tx,**kw):
                        if self.deny_replay:raise ReviewSubjectAccessDenied()
                owner,guard=SyntheticOwner(),auth.Guard()
                deps=dict(unit_of_work=runtime.unit_of_work,access=SqlAlchemyReviewStartAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository()),
                    license_guard=guard,repository=SqlAlchemyReviewTransitionRepository(),receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),subjects=owner)
                service=ReviewTransitionCommandService(**deps)
                def dc(pair,index=2):return DecideReviewRound(tokens[index],auth.CSRF,project,*pair,uuid.uuid4(),ReviewDecisionKind.APPROVE)
                def wc(pair,version=1):return WithdrawReviewRound(tokens[0],auth.CSRF,project,*pair,uuid.uuid4(),version,"合成测试：撤回原因")
                def run(c,key="synthetic-command-key",use=service):
                    return use.withdraw_idempotent(c,idempotency_key=key) if type(c) is WithdrawReviewRound else use.decide_idempotent(c,idempotency_key=key)
                def snapshot():return (schema.snapshot(db),tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")),
                    tuple(db.execute("SELECT * FROM plm.plt_idempotency_receipts ORDER BY receipt_id")),tuple(db.execute("SELECT * FROM public.synthetic_owner_consumption ORDER BY round_id")))
                def deny(c,code,key="synthetic-command-key",use=service):
                    before=snapshot()
                    try:run(c,key,use)
                    except ReviewTransitionCommandError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("unauthorized/failed command accepted")
                    assert snapshot()==before

                c=dc(pairs[0])
                for i in (0,1,4):deny(replace(c,session_token=tokens[i]),"RESOURCE_NOT_FOUND")
                for i in (1,2,3,4):deny(replace(wc(pairs[0]),session_token=tokens[i]),"RESOURCE_NOT_FOUND")
                deny(replace(c,csrf_token=b"x"*32),"AUTH_ACCESS_DENIED")
                deny(replace(c,project_id=uuid.uuid4()),"RESOURCE_NOT_FOUND")
                deny(c,"RESOURCE_NOT_FOUND",use=ReviewTransitionCommandService(**(deps|dict(subjects=None))))
                guard.enabled=False;deny(c,"LICENSE_OPERATION_DENIED");guard.enabled=True
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:run(c),range(2)))
                first=results[0]
                assert first==results[1] and first.state.value=="IN_REVIEW"
                assert db.execute("SELECT count(*) FROM plm.rvw_review_decisions WHERE review_round_id=%s",(c.round_id,)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s",(c.round_id,)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts").fetchone()[0]==1
                deny(replace(c,comment="Different request"),"CONFLICT_IDEMPOTENCY")
                deny(c,"REVIEW_DECISION_EXISTS",key="synthetic-distinct-command")
                owner.deny_replay=True;deny(c,"RESOURCE_NOT_FOUND");owner.deny_replay=False
                final=run(dc(pairs[0],3),"synthetic-final-command")
                assert final.state.value=="APPROVED" and run(c)==first
                with db.transaction():schema.start(db,c.review_id,users[0],tuple(users[2:4]))
                db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[3],))
                assert run(c)==first  # other historical reviewer disabled, no new approval
                db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(users[3],))

                w=wc(pairs[1])
                with ThreadPoolExecutor(max_workers=2) as pool:withdrawals=list(pool.map(lambda _:run(w,"synthetic-withdraw-command"),range(2)))
                withdrawn=withdrawals[0]
                assert withdrawn==withdrawals[1] and withdrawn.state.value=="WITHDRAWN"
                deny(replace(w,reason="Different reason"),"CONFLICT_IDEMPOTENCY",key="synthetic-withdraw-command")
                with db.transaction():schema.start(db,w.review_id,users[0],tuple(users[2:4]))
                assert run(w,"synthetic-withdraw-command")==withdrawn

                class FailedReceipt(SqlAlchemyIdempotencyReceipts):
                    def complete(self,*a,**kw):super().complete(*a,**kw);raise RuntimeError("synthetic receipt complete failure")
                for i,command_c in enumerate((dc(pairs[2]),wc(pairs[3]))):
                    deny(command_c,"REVIEW_UNAVAILABLE",key=f"synthetic-audit-failure-{i}",use=ReviewTransitionCommandService(**(deps|dict(audit=auth.FailedAudit()))))
                    deny(command_c,"REVIEW_UNAVAILABLE",key=f"synthetic-receipt-failure-{i}",use=ReviewTransitionCommandService(**(deps|dict(receipts=FailedReceipt()))))
                run(dc(pairs[4]),"synthetic-before-consume-failure")
                owner.fail_consume=True
                deny(dc(pairs[4],3),"REVIEW_UNAVAILABLE",key="synthetic-final-consume-failure")
                deny(wc(pairs[5]),"REVIEW_UNAVAILABLE",key="synthetic-withdraw-consume-failure")
                owner.fail_consume=False
                # All four Project roles are only the necessary policy superset.
                # This synthetic ALL policy is NOT customer-specific entitlement.
                for i in range(4):role_result=run(dc(allroles,i),f"synthetic-role-command-{i}")
                assert role_result.state.value=="APPROVED"

                authenticated,competitor_locked=Event(),Event()
                class DeadlockAccess(SqlAlchemyReviewStartAccess):
                    calls=0
                    def authenticated_user(self,tx,**kw):
                        self.calls+=1
                        tx.session.execute(text("SET LOCAL deadlock_timeout='50ms'"))
                        actor=super().authenticated_user(tx,**kw)
                        if self.calls==1:
                            authenticated.set();assert competitor_locked.wait(timeout=10)
                        return actor
                access=DeadlockAccess()
                def competitor():
                    assert authenticated.wait(timeout=10)
                    with schema.connect(name) as rival,rival.transaction():
                        rival.execute("SELECT 1 FROM plm.prj_projects WHERE project_id=%s FOR UPDATE",(project,))
                        competitor_locked.set()
                        rival.execute("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",(users[2],))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    rival=pool.submit(competitor)
                    recovered=run(dc(recovery),"synthetic-real-deadlock",ReviewTransitionCommandService(**(deps|dict(access=access))))
                    rival.result(timeout=10)
                assert access.calls==2 and recovered.state.value=="APPROVED"
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s",(recovery[1],)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id=%s",(recovered.event_id,)).fetchone()[0]==1
                assert db.execute("SELECT consumed FROM public.synthetic_owner_consumption WHERE round_id=%s",(recovery[1],)).fetchone()[0]==1

                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s",(users[2],))
                deny(c,"RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s",(users[2],))
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(w,"RESOURCE_NOT_FOUND",key="synthetic-withdraw-command")
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(project,))
                deny(c,"PROJECT_ARCHIVED");deny(w,"PROJECT_ARCHIVED",key="synthetic-withdraw-command")
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s",(users[2],))
                deny(c,"AUTH_ACCESS_DENIED")
            print("RVW-02-A09-P02 PASS: real Session/CSRF/Project/assigned or PM, owned Audit/receipt, concurrent immutable replay/changed payload, revoked access, consume/Audit/receipt rollback, REAL 40P01 whole-tx retry; TEST ONLY Owner/License, no HTTP/actual approval")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
