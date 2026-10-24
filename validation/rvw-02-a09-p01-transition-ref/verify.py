"""Immutable original response only; synthetic Owner, no auth/receipt/HTTP."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.review.application.persist_transition import ReviewTransitionPersistenceService
from plm_assistant.modules.review.infrastructure.transition_repository import SqlAlchemyReviewTransitionRepository
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind

spec = spec_from_file_location("_ref_fixture",Path(__file__).resolve().parents[1]/"rvw-02-a08-persist-transition"/"verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
schema = fixture.schema


class SyntheticOwner:
    """TEST ONLY no-op contract; DOES NOT validate real business lock/approval."""
    def require_transition_access_in_transaction(self,tx,intent): pass
    def assert_transition_lock_in_transaction(self,tx,intent): pass
    def consume_terminal_in_transaction(self,tx,intent): pass
    def assert_terminal_consumed_in_transaction(self,tx,intent): pass


def main():
    name,runtime = "reviewref_"+uuid.uuid4().hex[:12],None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head")
            runtime = create_database_runtime(url)
            with schema.connect(name) as db:
                users = [schema.insert(db,"auth_users",dict(username_display=f"Synthetic ref {i}",
                    username_normalized=f"synthetic ref {i}"),"user_id") for i in range(3)]
                actor,*reviewers = users
                project = schema.insert(db,"prj_projects",dict(project_code="REF",project_code_normalized="ref",
                    name="Synthetic immutable ref",created_by=actor),"project_id")
                review = schema.review(db,actor,project)
                with db.transaction(): round1,_,_ = schema.start(db,review,actor,tuple(reviewers))
                repo = SqlAlchemyReviewTransitionRepository()
                service = ReviewTransitionPersistenceService(repository=repo,audit=AuditService(SqlAlchemyAuditRepository()),subjects=SyntheticOwner())
                def decide(round_id,user,kind=ReviewDecisionKind.APPROVE):
                    with runtime.unit_of_work() as tx:
                        ref = service.decide_in_transaction(tx,actor_id=user,project_id=project,review_id=review,round_id=round_id,
                            trace_id=uuid.uuid4(),decision=kind,comment="Synthetic return" if kind is ReviewDecisionKind.RETURN else None)
                        tx.commit()
                        return ref
                def get(ref,**changes):
                    with runtime.unit_of_work() as tx:
                        return repo.get_transition_ref(tx,**(dict(project_id=project,review_id=review,
                            round_id=ref.round_id,event_id=ref.event_id)|changes))
                first = decide(round1,reviewers[0],ReviewDecisionKind.RETURN)
                assert first.state.value=="IN_REVIEW" and first.review_after_version==2
                assert get(first)==first
                final = decide(round1,reviewers[1])
                assert final.state.value=="RETURNED" and final.review_after_version==3
                assert get(first)==first and get(final)==final
                with db.transaction(): round2,_,_ = schema.start(db,review,actor,tuple(reviewers))
                second = decide(round2,reviewers[0])
                assert second.state.value=="IN_REVIEW" and second.review_after_version==5
                with runtime.unit_of_work() as tx:
                    withdrawn = service.withdraw_in_transaction(tx,actor_id=actor,project_id=project,review_id=review,
                        round_id=round2,trace_id=uuid.uuid4(),expected_version=5,reason="合成测试：撤回历史")
                    tx.commit()
                assert withdrawn.review_after_version==6 and withdrawn.state.value=="WITHDRAWN"
                assert get(second)==second and get(withdrawn)==withdrawn
                with db.transaction(): round3,_,_ = schema.start(db,review,actor,tuple(reviewers))
                assert get(first)==first and get(final)==final and get(second)==second and get(withdrawn)==withdrawn
                assert len({first.event_id,final.event_id,second.event_id,withdrawn.event_id})==4
                assert get(first,project_id=uuid.uuid4()) is None
                assert get(first,review_id=uuid.uuid4()) is None
                assert get(first,round_id=round3) is None
                assert get(first,event_id=uuid.uuid4()) is None
                noncommands = db.execute("SELECT round_event_id,review_round_id FROM plm.rvw_round_events WHERE event_type IN ('STARTED','COMPLETED')").fetchall()
                before = (schema.snapshot(db),tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")))
                for event,round_id in noncommands:
                    assert get(first,event_id=event,round_id=round_id) is None
                for ref in (first,final,second,withdrawn): assert get(ref)==ref
                assert (schema.snapshot(db),tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")))==before
            print("RVW-02-A09-P01 PASS: original command event Ref/state/counters/time/Actor unchanged after terminal/later rounds, first-return partial, withdrawal history, scoped/noncommand rejection, no read writes; synthetic Owner, auth/receipt/HTTP pending")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__": main()
