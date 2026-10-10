"""Trusted-caller persistence only; synthetic Subject Owner, no actual authorization."""
from dataclasses import replace
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid
from psycopg import sql
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.review.application.read_snapshot import ReviewBasisObservation
from plm_assistant.modules.review.application.subject_start import PreparedReviewSubject
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistenceService, ReviewRoundPersistError
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository
from plm_assistant.modules.review.infrastructure.read_repository import SqlAlchemyReviewSnapshotReadRepository

spec = spec_from_file_location("_round_persistence_fixture", Path(__file__).resolve().parents[1] / "rvw-01-a05-authorized-read" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
schema, auth = fixture.schema, fixture.auth


def main():
    name, runtime = "rvwpersist_"+uuid.uuid4().hex[:12], None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            with schema.connect(name) as db:
                users = [auth.user(db, f"Synthetic persistence {i}", bytes([i+1])*32) for i in range(3)]
                project = schema.insert(db, "prj_projects", dict(project_code="RP", project_code_normalized="rp", name="Synthetic persistence", created_by=users[0]), "project_id")
                evidence = schema.fixture.seed_evidence(db, project, users[0])
                reviews = [schema.review(db, users[0], project) for _ in range(6)]

                class SyntheticOwner:
                    """TEST ONLY binding/check-failure injector, NOT a real business lock."""
                    calls = 0
                    fail_at = None
                    stale_source = False
                    wrong_binding = False
                    def prepare_start_in_transaction(self, tx, request):
                        row = tx.session.execute(text("SELECT scope,project_id,eligibility_state,lock_version,content_fingerprint FROM plm.evd_evidence_records WHERE evidence_id=:id FOR SHARE"), dict(id=evidence)).one()
                        observed = datetime.now(timezone.utc)
                        basis = ReviewBasisObservation("EVIDENCE", evidence, row.scope, row.project_id, row.eligibility_state,
                            row.lock_version+(1 if self.stale_source else 0), bytes(row.content_fingerprint), observed)
                        if self.wrong_binding: request = replace(request, subject_version_id=uuid.uuid4())
                        return PreparedReviewSubject(request, b"s"*32, 1, datetime.now(timezone.utc), request.reviewer_ids, (basis,))
                    def assert_active_lock_in_transaction(self, tx, request):
                        self.calls += 1
                        if self.calls == self.fail_at: raise RuntimeError("synthetic Owner recheck failure")

                def service(owner, audit=None):
                    return ReviewRoundPersistenceService(repository=SqlAlchemyReviewStartRepository(),
                        audit=audit or AuditService(SqlAlchemyAuditRepository()), subjects=owner)
                def start(review, owner, audit=None, expected=0):
                    with runtime.unit_of_work() as tx:
                        result = service(owner,audit).start_in_transaction(tx, actor_id=users[0], project_id=project,
                            review_id=review, subject_version_id=uuid.uuid4(), reviewer_ids=tuple(users[1:]),
                            expected_version=expected, trace_id=uuid.uuid4())
                        tx.commit()
                        return result
                def snapshot():
                    return schema.snapshot(db), tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))
                for index, mode in enumerate(("first_lock", "second_lock", "audit", "source", "binding")):
                    before, owner = snapshot(), SyntheticOwner()
                    owner.fail_at = 1 if mode=="first_lock" else 2 if mode=="second_lock" else None
                    owner.stale_source, owner.wrong_binding = mode=="source", mode=="binding"
                    try: start(reviews[index], owner, auth.FailedAudit() if mode=="audit" else None)
                    except RuntimeError as exc:
                        assert mode in ("first_lock","second_lock","audit") and "synthetic" in str(exc)
                    except DBAPIError as exc:
                        assert mode=="source" and exc.orig.sqlstate=="P0001"
                    except ValueError:
                        assert mode=="binding"
                    else: raise AssertionError("failed preparation committed Review")
                    assert snapshot()==before
                owner = SyntheticOwner()
                result = start(reviews[5],owner)
                assert owner.calls==2
                with runtime.unit_of_work() as tx:
                    fixed = SqlAlchemyReviewSnapshotReadRepository().get_round(tx,"PROJECT",project,reviews[5],result.round_id)
                    assert fixed.progress.state.value=="IN_REVIEW" and fixed.round_lock_version==0
                    assert fixed.progress.reviewer_ids==tuple(sorted(users[1:])) and len(fixed.assignment_ids)==2
                    assert fixed.subject_version_id==result.subject_version_id and fixed.basis[0].ref_id==evidence
                    assert fixed.lock_released_at is None
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_STARTED'").fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.rvw_round_events WHERE event_type='STARTED'").fetchone()[0]==1
                before=snapshot()
                try: start(reviews[5],SyntheticOwner(),expected=1)
                except ReviewRoundPersistError as exc: assert exc.code=="REVIEW_SUBJECT_LOCKED"
                else: raise AssertionError("active Review started twice")
                assert snapshot()==before
            print("RVW-02-A05-P01 PASS: complete owned round/current root/snapshot/basis/assignments/lock/event + real Audit, before/after Owner and Audit/source/binding failure full rollback; trusted caller, synthetic Subject, not auth/start HTTP/Gate")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__": main()
