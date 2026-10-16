"""Real owned writes/Audit rollback; TEST ONLY Owner, no real customer approval."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
import uuid
from alembic import command
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.persist_transition import ReviewTransitionPersistenceService
from plm_assistant.modules.review.infrastructure.transition_repository import SqlAlchemyReviewTransitionRepository
from plm_assistant.modules.review.infrastructure.read_repository import SqlAlchemyReviewSnapshotReadRepository
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind

spec = spec_from_file_location("_transition_fixture", Path(__file__).resolve().parents[1]/"rvw-02-a05-p01-persistence"/"verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
schema, auth = fixture.schema, fixture.auth


def main():
    name, runtime = "reviewtransition_"+uuid.uuid4().hex[:12], None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url),"head")
            runtime = create_database_runtime(url)
            with schema.connect(name) as db:
                users = [schema.insert(db,"auth_users",dict(username_display=f"Synthetic transition {i}",
                    username_normalized=f"synthetic transition {i}"),"user_id") for i in range(4)]
                actor, reviewer_a, reviewer_b, outsider = users
                project = schema.insert(db,"prj_projects",dict(project_code="TRANSITION",project_code_normalized="transition",
                    name="Synthetic transition",created_by=actor),"project_id")
                # ONLY a disposable test marker. Not a production Subject table,
                # customer entitlement, immutable business version or real lock.
                db.execute("CREATE TABLE public.synthetic_owner_consumption(round_id uuid PRIMARY KEY, consumed integer NOT NULL DEFAULT 0, result_state text)")
                def seed(reviewers):
                    review = schema.review(db,actor,project)
                    with db.transaction():
                        round_id,_,_ = schema.start(db,review,actor,reviewers)
                        db.execute("INSERT INTO public.synthetic_owner_consumption(round_id) VALUES(%s)",(round_id,))
                    return review,round_id
                pairs = [seed((reviewer_a,reviewer_b)) for _ in range(10)]
                race = seed((reviewer_a,))

                class SyntheticOwner:
                    """TEST ONLY transaction marker/failure injector, NOT actual business Owner."""
                    def __init__(self,fail=None): self.fail,self.lock_checks = fail,0
                    def require_transition_access_in_transaction(self,tx,intent):
                        if self.fail=="access": raise RuntimeError("synthetic access failure")
                    def assert_transition_lock_in_transaction(self,tx,intent):
                        self.lock_checks += 1
                        value = tx.session.execute(text("SELECT consumed FROM public.synthetic_owner_consumption WHERE round_id=:id FOR UPDATE"),dict(id=intent.after_progress.round_id)).scalar_one()
                        assert value==0
                        if self.fail=="lock": raise RuntimeError("synthetic lock failure")
                        if self.fail=="second_lock" and self.lock_checks==2:
                            raise RuntimeError("synthetic second lock failure after owned write")
                    def consume_terminal_in_transaction(self,tx,intent):
                        assert intent.terminal
                        tx.session.execute(text("UPDATE public.synthetic_owner_consumption SET consumed=consumed+1,result_state=:state WHERE round_id=:id"),dict(id=intent.after_progress.round_id,state=intent.after_progress.state.value))
                        if self.fail=="consume": raise RuntimeError("synthetic failure after consumption write")
                        if self.fail=="bool": return True
                    def assert_terminal_consumed_in_transaction(self,tx,intent):
                        value = tx.session.execute(text("SELECT consumed,result_state FROM public.synthetic_owner_consumption WHERE round_id=:id"),dict(id=intent.after_progress.round_id)).one()
                        assert tuple(value)==(1,intent.after_progress.state.value)
                        if self.fail=="consumed_check": raise RuntimeError("synthetic consumed recheck failure")

                repo = SqlAlchemyReviewTransitionRepository()
                audit = AuditService(SqlAlchemyAuditRepository())
                def run(pair,*,withdraw=False,reviewer=reviewer_a,decision=ReviewDecisionKind.APPROVE,
                        owner=None,expected=1,audit_port=None,reason=None,project_override=None):
                    service = ReviewTransitionPersistenceService(repository=repo,audit=audit_port or audit,
                        subjects=owner if owner is not None else SyntheticOwner())
                    with runtime.unit_of_work() as tx:
                        args = dict(actor_id=actor if withdraw else reviewer,project_id=project_override or project,
                            review_id=pair[0],round_id=pair[1],trace_id=uuid.uuid4())
                        result = service.withdraw_in_transaction(tx,**args,expected_version=expected,reason=reason) if withdraw else service.decide_in_transaction(
                            tx,**args,decision=decision,comment="Synthetic correction" if decision is ReviewDecisionKind.RETURN else None)
                        tx.commit()
                        return result
                def get(pair):
                    with runtime.unit_of_work() as tx:
                        return SqlAlchemyReviewSnapshotReadRepository().get_round(tx,"PROJECT",project,*pair)
                def snapshot():
                    return (schema.snapshot(db),tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")),
                            tuple(db.execute("SELECT * FROM public.synthetic_owner_consumption ORDER BY round_id")))
                def reject(action):
                    before = snapshot()
                    try: action()
                    except (ValueError,RuntimeError):
                        assert snapshot()==before
                        return
                    raise AssertionError("failed transition committed")

                pair = pairs[0]
                first = run(pair)
                assert first.state.value=="IN_REVIEW" and first.review_after_version==2
                assert get(pair).lock_released_at is None
                assert db.execute("SELECT consumed FROM public.synthetic_owner_consumption WHERE round_id=%s",(pair[1],)).fetchone()[0]==0
                reject(lambda:run(pair))  # distinct command cannot overwrite reviewer decision
                reject(lambda:run(pair,reviewer=outsider))
                reject(lambda:run(pair,project_override=uuid.uuid4()))
                final = run(pair,reviewer=reviewer_b)
                assert final.state.value=="APPROVED" and final.round_after_version==2 and final.review_after_version==3
                assert get(pair).lock_released_at is not None
                assert db.execute("SELECT consumed,result_state FROM public.synthetic_owner_consumption WHERE round_id=%s",(pair[1],)).fetchone()==(1,"APPROVED")
                reject(lambda:run(pair,withdraw=True,expected=3))

                pair = pairs[1]
                run(pair,decision=ReviewDecisionKind.RETURN)
                assert get(pair).progress.state.value=="IN_REVIEW" and get(pair).lock_released_at is None
                assert run(pair,reviewer=reviewer_b).state.value=="RETURNED"

                pair = pairs[2]
                run(pair)
                reject(lambda:run(pair,withdraw=True,expected=1,reason="Synthetic stale"))
                result = run(pair,withdraw=True,expected=2,reason="合成测试：重新调整范围")
                fixed = get(pair)
                assert result.state.value=="WITHDRAWN" and len(fixed.progress.decisions)==1
                assert fixed.progress.pending_reviewer_ids==(reviewer_b,)
                assert fixed.progress.withdrawal.reason=="合成测试：重新调整范围"

                for pair,mode in zip(pairs[3:9],("access","lock","second_lock","consume","bool","consumed_check")):
                    run(pair)
                    reject(lambda pair=pair,mode=mode:run(pair,reviewer=reviewer_b,owner=SyntheticOwner(mode)))
                    assert get(pair).progress.state.value=="IN_REVIEW"
                    assert len(get(pair).progress.decisions)==1 and get(pair).lock_released_at is None
                pair = pairs[9]
                run(pair)
                reject(lambda:run(pair,reviewer=reviewer_b,audit_port=auth.FailedAudit()))
                reject(lambda:run(pair,withdraw=True,expected=2,reason="Synthetic rollback",owner=SyntheticOwner("consume")))
                reject(lambda:run(pair,withdraw=True,expected=2,reason="Synthetic rollback",audit_port=auth.FailedAudit()))

                barrier = Barrier(2)
                def compete(withdraw):
                    barrier.wait(timeout=5)
                    try: return run(race,withdraw=withdraw,expected=1,reason="Synthetic race" if withdraw else None).state.value
                    except ReviewRoundPersistError as exc: return exc.code
                with ThreadPoolExecutor(max_workers=2) as pool:
                    left,right = pool.submit(compete,False),pool.submit(compete,True)
                    results = (left.result(timeout=10),right.result(timeout=10))
                assert sum(r in ("APPROVED","WITHDRAWN") for r in results)==1, results
                assert db.execute("SELECT consumed FROM public.synthetic_owner_consumption WHERE round_id=%s",(race[1],)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s",(race[1],)).fetchone()[0]==1
                fixed = get(race)
                assert fixed.progress.state.value in ("APPROVED","WITHDRAWN") and fixed.lock_released_at is not None
            print("RVW-02-A08 PASS: real owned decision/withdrawal/events/Audit, complete-set/history/reason, final decision-vs-withdraw winner, failed Owner/Audit whole-tx rollback; TEST ONLY Owner, no auth/receipt/HTTP/actual approval")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__": main()
