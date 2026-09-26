"""Internal caller-tx snapshot proof, no actual reviewer/Subject authorization."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import uuid
import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.review.infrastructure.read_repository import SqlAlchemyReviewSnapshotReadRepository

spec = spec_from_file_location("_review_read_fixture", Path(__file__).resolve().parents[1] / "rvw-01-a02-review-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    name = "reviewread_"+uuid.uuid4().hex[:12]
    engine = None
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url)
            repository = SqlAlchemyReviewSnapshotReadRepository()
            with fixture.connect(name) as db:
                users = [fixture.insert(db, "auth_users", dict(username_display=f"Synthetic read {i}", username_normalized=f"synthetic read {i}"), "user_id") for i in range(3)]
                actor, *reviewers = users
                project = fixture.insert(db, "prj_projects", dict(project_code="READ", project_code_normalized="read", name="Synthetic review read", created_by=actor), "project_id")
                evidence = fixture.fixture.seed_evidence(db, project, actor)
                identity = fixture.review(db, actor, project)
                global_review = fixture.review(db, actor, None)

                def get(round_id=None, *, scope="PROJECT", p=project, review_id=identity):
                    with Session(engine) as session, session.begin():
                        tx = SimpleNamespace(session=session)
                        return repository.get_review(tx, scope, p, review_id) if round_id is None else repository.get_round(tx, scope, p, review_id, round_id)

                before = fixture.snapshot(db)
                assert get().state == "DRAFT"
                assert get(uuid.uuid4()) is None and get(p=uuid.uuid4()) is None
                assert get(scope="GLOBAL", p=None) is None
                assert get(scope="GLOBAL", p=None, review_id=global_review).state == "DRAFT"
                assert fixture.snapshot(db) == before
                with db.transaction():
                    round_id, _, _ = fixture.start(db, identity, actor, reviewers, evidence)
                active = get(round_id)
                assert active.progress.state.value == "IN_REVIEW" and active.lock_released_at is None
                assert active.progress.pending_reviewer_ids == tuple(sorted(reviewers))
                with db.transaction():
                    fixture.decide(db, round_id, reviewers[0], "RETURN", comment="Synthetic requested clarification")
                partial = get(round_id)
                assert partial.progress.state.value == "IN_REVIEW" and len(partial.progress.decisions) == 1
                with db.transaction():
                    fixture.decide(db, round_id, reviewers[1])
                returned = get(round_id)
                assert returned.progress.state.value == "RETURNED" and returned.lock_released_at is not None
                assert returned.progress.decisions[0].comment is not None or returned.progress.decisions[1].comment is not None
                with db.transaction():
                    later_round, _, _ = fixture.start(db, identity, actor, reviewers, evidence)
                    fixture.decide(db, later_round, reviewers[0])
                historical = get(round_id)
                assert historical.progress.state.value == "RETURNED" and historical.review.state == "IN_REVIEW"
                assert historical.subject_version_id == returned.subject_version_id
                with db.transaction():
                    fixture.withdraw(db, later_round, actor)
                withdrawn = get(later_round)
                assert withdrawn.progress.state.value == "WITHDRAWN" and len(withdrawn.progress.decisions) == 1
                assert len(withdrawn.progress.pending_reviewer_ids) == 1
                db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',eligibility_reason='Synthetic later change',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
                assert get(round_id).basis[0].observed_state == "ELIGIBLE"
                with db.transaction():
                    global_round, _, _ = fixture.start(db, global_review, actor, reviewers[:1])
                    fixture.decide(db, global_round, reviewers[0])
                approved = get(global_round, scope="GLOBAL", p=None, review_id=global_review)
                assert approved.review.project_id is None and approved.progress.state.value == "APPROVED"
                assert get(global_round) is None and get(scope="PROJECT", review_id=global_review) is None
                # Shared Review lock blocks a writer until the caller transaction finishes.
                def rival_write():
                    with fixture.connect(name) as rival:
                        rival.execute("SET lock_timeout='150ms'")
                        try:
                            with rival.transaction():
                                fixture.start(rival, identity, actor, reviewers)
                        except psycopg.errors.LockNotAvailable:
                            return "locked"
                        raise AssertionError("Review writer escaped read transaction")
                before = fixture.snapshot(db)
                with Session(engine) as session, session.begin():
                    repository.get_round(SimpleNamespace(session=session), "PROJECT", project, identity, round_id)
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        assert pool.submit(rival_write).result() == "locked"
                assert fixture.snapshot(db) == before
                with db.transaction():
                    fixture.start(db, identity, actor, reviewers)
                with Session(engine) as session:
                    try:
                        repository.get_review(SimpleNamespace(session=session), "PROJECT", project, identity)
                    except RuntimeError:
                        assert not session.in_transaction()
                    else:
                        raise AssertionError("implicit caller transaction accepted")
            print("RVW-01-A03 PASS: scoped fixed round/current identity, complete decisions/withdrawal/history/basis, no writes, caller lock; synthetic Subjects/reviewer资格, not Gate proof")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
