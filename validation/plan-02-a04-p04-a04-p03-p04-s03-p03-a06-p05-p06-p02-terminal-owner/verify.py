"""Synthetic Win11/PG18 PlanVersion Review terminal Owner acceptance.

Uses real PostgreSQL migrations, Review/Round, Owner, Audit, Plan result and
receipt transactions. Session, License, project policy, reviewer facts and the
source-current validation evaluator are deterministic test doubles only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.plan.application.plan_review_readiness import PlanVersionReviewReadinessService
from plm_assistant.modules.plan.application.plan_version_review_terminal import PlanVersionReviewSubjectOwner
from plm_assistant.modules.plan.application.submit_plan_version_review import SubmitPlanVersionReview, PlanVersionReviewSubmissionService
from plm_assistant.modules.plan.application.validate_plan_version_contract import PlanVersionCoverageSummary, PlanVersionValidationReport
from plm_assistant.modules.plan.infrastructure.orm import PlanRow, PlanVersionReviewStateResultRow, PlanVersionRow
from plm_assistant.modules.plan.infrastructure.plan_review_readiness_repository import SqlAlchemyPlanVersionReviewReadinessRepository
from plm_assistant.modules.plan.infrastructure.plan_review_subject_repository import SqlAlchemyPlanReviewSubjectRepository
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.project.application.reviewers import ProjectReviewerFacts
from plm_assistant.modules.review.application.project_persistence import ProjectReviewPersistenceService
from plm_assistant.modules.review.application.transition_command import DecideReviewRound, WithdrawReviewRound, ReviewTransitionCommandService, ReviewTransitionCommandError
from plm_assistant.modules.review.application.subject_registry import ProjectReviewSubjectRegistry
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.create_repository import SqlAlchemyReviewCreationRepository
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository
from plm_assistant.modules.review.infrastructure.project_submission_repository import SqlAlchemyProjectReviewSubmissionRepository
from plm_assistant.modules.review.infrastructure.transition_repository import SqlAlchemyReviewTransitionRepository
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


def main(port: int) -> None:
    def connect(name: str):
        return psycopg.connect(host="127.0.0.1", port=port, user="poc_admin", dbname=name,
                               autocommit=True, connect_timeout=5)

    db_name = "plnterminal_" + uuid.uuid4().hex[:10]
    created = False
    with connect("postgres") as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            created = True
            config = create_migration_config(URL.create("postgresql+psycopg", username="poc_admin",
                                                        host="127.0.0.1", port=port, database=db_name))
            command.upgrade(config, "head")
            command.check(config)
            project, manager, reviewer, trace = (uuid.uuid4() for _ in range(4))
            plan_a = uuid.uuid4()
            plans = [(plan_a, uuid.uuid4()), (plan_a, uuid.uuid4()),
                     (plan_a, uuid.uuid4())]
            now = datetime.now(timezone.utc)
            with connect(db_name) as db, db.transaction():
                for uid, tag in ((manager, "manager"), (reviewer, "reviewer")):
                    name = f"synthetic terminal {tag} {db_name}"
                    db.execute("INSERT INTO plm.auth_users(user_id,username_display,username_normalized) VALUES (%s,%s,%s)", (uid, name, name))
                suffix = db_name[-6:]
                db.execute("INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)",
                           (project, "PTR"+suffix, "ptr"+suffix, "Synthetic Plan Terminal", manager))
                for index, (plan_id, version_id) in enumerate(plans, 1):
                    if index > 1:
                        continue
                    db.execute("INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) VALUES (%s,%s,%s,%s)",
                               (plan_id, project, f"Synthetic Plan {index}", manager))
                    db.execute("INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) SELECT plan_id,project_id,name,created_at FROM plm.pln_plans WHERE plan_id=%s", (plan_id,))
                    db.execute("INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) VALUES (%s,%s,%s,1,%s)",
                               (version_id, plan_id, project, manager))

            engine = create_engine(URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=port, database=db_name))
            try:
                factory = sessionmaker(engine, expire_on_commit=False)
                uow = lambda: SqlAlchemyUnitOfWork(factory)
                current_actor = {"id": manager}
                access, projects, license_guard = Mock(), Mock(), Mock()
                access.authenticated_user.side_effect = lambda *a, **kw: current_actor["id"]
                def authorize(tx, *, user_id, project_id, operation):
                    role = "PROJECT_MANAGER" if operation in ("PLAN_VERSION_SUBMIT_REVIEW", "WITHDRAW", "REVIEW_WITHDRAW") else "CUSTOMER_MANAGER"
                    return AuthorizedProjectAction(user_id, project_id, operation, role)
                projects.require_in_transaction.side_effect = authorize
                reviewer_facts = Mock()
                reviewer_facts.qualify_in_transaction.side_effect = lambda tx, *, project_id, reviewer_ids, allowed_roles: tuple(
                    ProjectReviewerFacts(user_id, project_id,
                        "PROJECT_MANAGER" if user_id == manager else "CUSTOMER_MANAGER")
                    for user_id in reviewer_ids)
                summary = PlanVersionCoverageSummary(0, 0, 0, 0, 0, 0, 0, 0)
                report = PlanVersionValidationReport(True, (), (), summary, now)
                evaluator = Mock()
                def evaluate(tx, *, snapshot, **kwargs):
                    payload = json.dumps(snapshot.snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
                    return hashlib.sha256(payload).digest(), report
                evaluator.evaluate_snapshot_in_transaction.side_effect = evaluate
                readiness = PlanVersionReviewReadinessService(repository=SqlAlchemyPlanVersionReviewReadinessRepository(), evaluator=evaluator)
                audit = AuditService(SqlAlchemyAuditRepository())
                owner = PlanVersionReviewSubjectOwner(repository=SqlAlchemyPlanReviewSubjectRepository(), reviewers=reviewer_facts, readiness=readiness, audit=audit)
                subject_registry = ProjectReviewSubjectRegistry((owner,))
                receipts = SqlAlchemyIdempotencyReceipts()
                starts = SqlAlchemyReviewStartRepository()
                persistence = ProjectReviewPersistenceService(creation_repository=SqlAlchemyReviewCreationRepository(), round_repository=starts, audit=audit, subjects=subject_registry, clock=lambda: now)
                submit = PlanVersionReviewSubmissionService(unit_of_work=uow, access=access, license_guard=license_guard,
                    authorization=projects, reviewers=Mock(), receipts=receipts,
                    replay_repository=SqlAlchemyProjectReviewSubmissionRepository(), reviews=persistence,
                    subjects=subject_registry, scope_repository=SqlAlchemyPlanReviewSubjectRepository(), clock=lambda: now)
                transition = ReviewTransitionCommandService(unit_of_work=uow, access=access, projects=projects,
                    license_guard=license_guard, repository=SqlAlchemyReviewTransitionRepository(), receipts=receipts,
                    audit=audit, subjects=subject_registry, clock=lambda: now)
                started = []
                for index, (plan_id, version_id) in enumerate(plans):
                    if index > 0:
                        with connect(db_name) as db, db.transaction():
                            db.execute("INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) VALUES (%s,%s,%s,%s,%s)",
                                       (version_id, plan_id, project, index + 1, manager))
                    current_actor["id"] = manager
                    item = submit.submit(SubmitPlanVersionReview(b"s"*32, b"c"*32, trace, project, plan_id,
                        version_id, (reviewer,), "PLAN_VERSION_ALL_V1", str(uuid.uuid4())))
                    started.append(item)
                    if index < 2:
                        current_actor["id"] = reviewer
                        command_obj = DecideReviewRound(b"s"*32, b"c"*32, project, item.review_id, item.round_id, trace, ReviewDecisionKind.APPROVE)
                        key = str(uuid.uuid4())
                        applied = transition.decide_idempotent(command_obj, idempotency_key=key)
                        assert transition.decide_idempotent(command_obj, idempotency_key=key) == applied
                        assert transition.decide_idempotent(command_obj, idempotency_key=key) == applied
                # Third submitted Review is withdrawn by current Project Manager.
                item = started[2]
                current_actor["id"] = manager
                withdraw = WithdrawReviewRound(b"s"*32, b"c"*32, project, item.review_id, item.round_id, trace, 1, "synthetic withdrawal")
                key = str(uuid.uuid4())
                class FailPlanTerminalAudit:
                    def append(self, tx, event):
                        if event.action == "PLAN_VERSION_REVIEW_WITHDRAWN":
                            raise RuntimeError("synthetic Plan terminal Audit failure")
                        return audit.append(tx, event)
                failing_owner = PlanVersionReviewSubjectOwner(
                    repository=SqlAlchemyPlanReviewSubjectRepository(),
                    reviewers=reviewer_facts, readiness=readiness,
                    audit=FailPlanTerminalAudit())
                failing_registry = ProjectReviewSubjectRegistry((failing_owner,))
                failing_transition = ReviewTransitionCommandService(
                    unit_of_work=uow, access=access, projects=projects,
                    license_guard=license_guard,
                    repository=SqlAlchemyReviewTransitionRepository(),
                    receipts=receipts, audit=audit, subjects=failing_registry,
                    clock=lambda: now)
                try:
                    failing_transition.withdraw_idempotent(withdraw, idempotency_key=key)
                except ReviewTransitionCommandError as error:
                    assert error.code == "REVIEW_UNAVAILABLE"
                else:
                    raise AssertionError("synthetic terminal Audit failure did not abort withdrawal")
                with factory() as session:
                    assert session.get(PlanVersionRow, plans[2][1]).version_state == "IN_REVIEW"
                    assert session.execute(text("SELECT count(*) FROM plm.rvw_round_events WHERE review_round_id=:id AND event_type='WITHDRAWN'"), {"id": item.round_id}).scalar_one() == 0
                    assert session.execute(text("SELECT count(*) FROM plm.pln_plan_version_review_state_results WHERE plan_version_id=:id AND event_type='WITHDRAWN'"), {"id": plans[2][1]}).scalar_one() == 0
                    assert session.execute(text("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_REVIEW_WITHDRAW' AND request_fingerprint IS NOT NULL")).scalar_one() == 0
                applied = transition.withdraw_idempotent(withdraw, idempotency_key=key)
                assert transition.withdraw_idempotent(withdraw, idempotency_key=key) == applied

                with factory() as session:
                    states = {row.plan_version_id: row.version_state for row in session.query(PlanVersionRow).all()}
                    assert states[plans[0][1]] == "SUPERSEDED"
                    assert states[plans[1][1]] == "APPROVED"
                    assert states[plans[2][1]] == "RETURNED"
                    plan = session.get(PlanRow, plans[1][0])
                    assert plan.current_approved_version_ref == plans[1][1]
                    events = session.query(PlanVersionReviewStateResultRow).all()
                    assert sorted(row.event_type for row in events).count("APPROVED") == 2
                    assert sorted(row.event_type for row in events).count("SUPERSEDED") == 1
                    withdrawn = [row for row in events if row.event_type == "WITHDRAWN"]
                    assert len(withdrawn) == 1 and withdrawn[0].current_state == "RETURNED"
                    assert session.execute(text("SELECT count(*) FROM plm.rvw_round_events WHERE event_type='WITHDRAWN'")).scalar_one() == 1
                    assert session.execute(text("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_REVIEW_DECIDE'")).scalar_one() == 2
                    assert session.execute(text("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_REVIEW_WITHDRAW'")).scalar_one() == 1
                    assert session.execute(text("SELECT count(*) FROM plm.aud_events WHERE action LIKE 'PLAN_VERSION_REVIEW_%'")).scalar_one() == 3
                try:
                    command.downgrade(config, "20261026_0200")
                except RuntimeError as error:
                    assert "withdrawn Plan Review history prevents downgrade" in str(error)
                else:
                    raise AssertionError("migration 0210 allowed loss of real withdrawal history")
                with connect(db_name) as db:
                    assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20261026_0210"
                print("PLAN_VERSION_REVIEW_REGISTRY_TERMINAL_PG_PASS: real Migrations 0210/0200/0190, ProjectReviewSubjectRegistry, Approved pointer, old Approved SUPERSEDED, WITHDRAWN-to-RETURNED result, Review+Plan Audits, receipts and exact idempotent replays; Session/License/Project/reviewer/source proof test doubles")
            finally:
                engine.dispose()
        finally:
            if created:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (db_name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    main(parser.parse_args().port)
