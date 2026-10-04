"""Disposable PostgreSQL 18 proof for the Review-owned GLOBAL kernel."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.review.application.global_persistence import (
    GlobalReviewPersistenceService,
)
from plm_assistant.modules.review.application.subject_start import (
    PreparedReviewSubject,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.global_repository import (
    SqlAlchemyGlobalReviewRepository,
)


ROOT = Path(__file__).resolve().parents[2]
_seed = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, seed_user = _seed["connect"], _seed["seed_user"]


class BoundSyntheticOwner:
    """A02 fixture only; A03 replaces this with the real Capability Owner."""

    def __init__(self, now):
        self.now = now
        self.consumed = []

    def prepare_start_in_transaction(self, tx, request):
        return PreparedReviewSubject(
            request, b"g" * 32, 1, self.now, request.reviewer_ids, (),
        )

    def assert_active_lock_in_transaction(self, tx, request):
        return None

    def finalize_start_in_transaction(self, tx, request):
        return None

    def require_start_replay_access_in_transaction(self, **kwargs):
        return None

    def require_transition_access_in_transaction(self, tx, transition):
        return None

    def assert_transition_lock_in_transaction(self, tx, transition):
        return None

    def consume_terminal_in_transaction(self, tx, transition):
        self.consumed.append((transition.before.review.review_id,
                              transition.after_progress.state.value))
        return None

    def assert_terminal_consumed_in_transaction(self, tx, transition):
        expected = (transition.before.review.review_id,
                    transition.after_progress.state.value)
        if not self.consumed or self.consumed[-1] != expected:
            raise AssertionError("synthetic terminal consumption missing")
        return None

    def require_transition_replay_access_in_transaction(self, **kwargs):
        return None


def main() -> None:
    name = "cap01a04a02_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    submitter = seed_user(
                        db, "Synthetic Global Submitter", "DEPLOYMENT_ADMIN",
                        b"a" * 32,
                    )
                    reviewer_one = seed_user(
                        db, "Synthetic Global Reviewer One", "NONE",
                        b"b" * 32,
                    )
                    reviewer_two = seed_user(
                        db, "Synthetic Global Reviewer Two", "NONE",
                        b"c" * 32,
                    )
                now = datetime.now(timezone.utc)
                owner = BoundSyntheticOwner(now)
                repository = SqlAlchemyGlobalReviewRepository()
                service = GlobalReviewPersistenceService(
                    repository=repository,
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    subjects=owner, clock=lambda: now,
                )
                subject_id, version_id = uuid.uuid4(), uuid.uuid4()
                with runtime.unit_of_work() as tx:
                    submitted = service.submit_in_transaction(
                        tx, actor_id=submitter, subject_type="CAP-01",
                        subject_id=subject_id,
                        subject_version_id=version_id,
                        reviewer_ids=(reviewer_one, reviewer_two),
                        policy_code="DEPLOYMENT_ALL_V1",
                        trace_id=uuid.uuid4(),
                    )
                    tx.commit()
                with runtime.unit_of_work() as tx:
                    partial = service.decide_in_transaction(
                        tx, actor_id=reviewer_one,
                        review_id=submitted.review_id,
                        round_id=submitted.round_id,
                        trace_id=uuid.uuid4(),
                        decision=ReviewDecisionKind.APPROVE,
                    )
                    assert partial.state.value == "IN_REVIEW"
                    tx.commit()
                with runtime.unit_of_work() as tx:
                    completed = service.decide_in_transaction(
                        tx, actor_id=reviewer_two,
                        review_id=submitted.review_id,
                        round_id=submitted.round_id,
                        trace_id=uuid.uuid4(),
                        decision=ReviewDecisionKind.APPROVE,
                    )
                    assert completed.state.value == "APPROVED"
                    tx.commit()

                with runtime.unit_of_work() as tx:
                    withdrawn = service.submit_in_transaction(
                        tx, actor_id=submitter, subject_type="CAP-01",
                        subject_id=subject_id,
                        subject_version_id=uuid.uuid4(),
                        reviewer_ids=(reviewer_one,),
                        policy_code="DEPLOYMENT_ALL_V1",
                        trace_id=uuid.uuid4(),
                    )
                    tx.commit()
                with runtime.unit_of_work() as tx:
                    result = service.withdraw_in_transaction(
                        tx, actor_id=submitter,
                        review_id=withdrawn.review_id,
                        round_id=withdrawn.round_id,
                        trace_id=uuid.uuid4(), expected_version=1,
                        reason="synthetic scope change",
                    )
                    assert result.state.value == "WITHDRAWN"
                    tx.commit()

                with connect(name) as db:
                    rows = db.execute("""
                        SELECT review_state,scope,project_id,lock_version
                          FROM plm.rvw_reviews ORDER BY created_at,review_id
                    """).fetchall()
                    assert rows == [
                        ("APPROVED", "GLOBAL", None, 3),
                        ("WITHDRAWN", "GLOBAL", None, 2),
                    ], rows
                    assert db.execute("""
                        SELECT count(*) FROM plm.rvw_reviews
                         WHERE scope='PROJECT' OR project_id IS NOT NULL
                    """).fetchone()[0] == 0
                    assert db.execute("""
                        SELECT count(*) FROM plm.rvw_subject_locks
                         WHERE scope='GLOBAL' AND project_id IS NULL
                           AND lock_state='RELEASED'
                    """).fetchone()[0] == 2
                    assert db.execute("""
                        SELECT count(*) FROM plm.rvw_round_events
                         WHERE scope='GLOBAL' AND project_id IS NULL
                    """).fetchone()[0] == 6
                    assert db.execute("""
                        SELECT count(*) FROM plm.aud_events
                         WHERE event_scope='DEPLOYMENT'
                           AND action IN ('REVIEW_CREATED','REVIEW_STARTED',
                                          'REVIEW_DECISION_RECORDED',
                                          'REVIEW_WITHDRAWN')
                    """).fetchone()[0] == 7
                assert owner.consumed == [
                    (submitted.review_id, "APPROVED"),
                    (withdrawn.review_id, "WITHDRAWN"),
                ]
                print(
                    "CAP_01_A04_A02_GLOBAL_REVIEW_KERNEL_PASS: GLOBAL submit, "
                    "multi-reviewer approval, withdrawal, Audit, subject terminal "
                    "consumption and Scope isolation verified on PostgreSQL"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
