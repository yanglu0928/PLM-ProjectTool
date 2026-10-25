"""Win11/PG18 atomic Plan SubmitReview and Migration 0190 closure proof.

Synthetic Plan and identity fixtures only. Current source/validation evaluator,
Session authentication, Project authorization, License and reviewer services
are deliberate test doubles; this validates same-transaction persistence and
database closure, not source eligibility or a production trust composition.
"""

from __future__ import annotations

import argparse
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
from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanVersionReviewReadinessService,
)
from plm_assistant.modules.plan.application.plan_review_subject import PlanReviewSubjectOwner
from plm_assistant.modules.plan.application.submit_plan_version_review import (
    PlanVersionReviewSubmissionError, PlanVersionReviewSubmissionService,
    SubmitPlanVersionReview,
)
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanVersionReviewStateResultRow, PlanVersionRow,
)
from plm_assistant.modules.plan.infrastructure.plan_review_readiness_repository import (
    SqlAlchemyPlanVersionReviewReadinessRepository,
)
from plm_assistant.modules.plan.infrastructure.plan_review_subject_repository import (
    SqlAlchemyPlanReviewSubjectRepository,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.project.application.reviewers import ProjectReviewerFacts
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.project_submission_repository import (
    SqlAlchemyProjectReviewSubmissionRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionCoverageSummary, PlanVersionValidationReport,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


USER = "poc_admin"


def main(port: int) -> None:
    def connect(name: str) -> psycopg.Connection:
        return psycopg.connect(host="127.0.0.1", port=port, user=USER,
                               dbname=name, autocommit=True, connect_timeout=5)

    def migration(name: str):
        return create_migration_config(URL.create(
            "postgresql+psycopg", username=USER, host="127.0.0.1",
            port=port, database=name))

    db_name = "plnsubmit_" + uuid.uuid4().hex[:10]
    created = False
    with connect("postgres") as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            created = True
            config = migration(db_name)
            command.upgrade(config, "head")
            command.check(config)
            project, plan, version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            actor, reviewer, trace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            now = datetime.now(timezone.utc)
            with connect(db_name) as db, db.transaction():
                for suffix, user_id in (("manager", actor), ("reviewer", reviewer)):
                    name = f"synthetic plan review {suffix} {db_name}"
                    db.execute(
                        "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                        "VALUES (%s,%s,%s)",
                        (user_id, name, name),
                    )
                tag = db_name[-6:]
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (project, "PSR" + tag, "psr" + tag,
                     "Synthetic Plan SubmitReview", actor),
                )
                db.execute(
                    "INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) "
                    "VALUES (%s,%s,%s,%s)",
                    (plan, project, "Synthetic Plan", actor),
                )
                db.execute(
                    "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                    "SELECT plan_id,project_id,name,created_at FROM plm.pln_plans WHERE plan_id=%s",
                    (plan,),
                )
                db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) "
                    "VALUES (%s,%s,%s,1,%s)", (version, plan, project, actor),
                )

            engine = create_engine(URL.create(
                "postgresql+psycopg", username=USER, host="127.0.0.1",
                port=port, database=db_name))
            try:
                factory = sessionmaker(engine, expire_on_commit=False)
                uow = lambda: SqlAlchemyUnitOfWork(factory)
                reviewer_facts = Mock()
                reviewer_facts.qualify_in_transaction.return_value = (
                    ProjectReviewerFacts(reviewer, project, "CUSTOMER_MANAGER"),)
                evaluator = Mock()
                valid_report = PlanVersionValidationReport(
                    True, (), (), PlanVersionCoverageSummary(0, 0, 0, 0, 0, 0, 0, 0), now)
                invalid_report = PlanVersionValidationReport(
                    False, ("APPROVED_SOURCE_UNAVAILABLE",), (),
                    PlanVersionCoverageSummary(0, 0, 0, 0, 0, 0, 0, 0), now)
                evaluator.evaluate_snapshot_in_transaction.side_effect = [
                    (b"p" * 32, invalid_report),
                    (b"p" * 32, valid_report),
                    (b"p" * 32, valid_report),
                ]
                readiness = PlanVersionReviewReadinessService(
                    repository=SqlAlchemyPlanVersionReviewReadinessRepository(),
                    evaluator=evaluator,
                )
                subject = PlanReviewSubjectOwner(
                    repository=SqlAlchemyPlanReviewSubjectRepository(),
                    reviewers=reviewer_facts, readiness=readiness,
                )
                review_repository = SqlAlchemyReviewStartRepository()
                audit = AuditService(SqlAlchemyAuditRepository())
                access, license_guard, authorization = Mock(), Mock(), Mock()
                access.authenticated_user.return_value = actor
                authorization.require_in_transaction.return_value = AuthorizedProjectAction(
                    actor, project, "PLAN_VERSION_SUBMIT_REVIEW", "PROJECT_MANAGER")
                submission_reviewers = Mock()
                receipts = SqlAlchemyIdempotencyReceipts()
                def build_service(audit_port):
                    persistence = ProjectReviewPersistenceService(
                        creation_repository=SqlAlchemyReviewCreationRepository(),
                        round_repository=review_repository, audit=audit_port,
                        subjects=subject, clock=lambda: now,
                    )
                    return PlanVersionReviewSubmissionService(
                        unit_of_work=uow, access=access,
                        license_guard=license_guard,
                        authorization=authorization,
                        reviewers=submission_reviewers, receipts=receipts,
                        replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
                        reviews=persistence, subjects=subject,
                        scope_repository=SqlAlchemyPlanReviewSubjectRepository(),
                        clock=lambda: now,
                    )
                submit_command = SubmitPlanVersionReview(
                    b"s" * 32, b"c" * 32, trace, project, plan, version,
                    (reviewer,), "PLAN_VERSION_ALL_V1", str(uuid.uuid4()),
                )
                try:
                    build_service(audit).submit(submit_command)
                except PlanVersionReviewSubmissionError as error:
                    assert error.code == "BUSINESS_REVIEW_NOT_ELIGIBLE"
                else:
                    raise AssertionError("invalid current-fact proof was submitted")
                with factory() as session:
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.rvw_reviews")).scalar_one() == 0
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.aud_events")).scalar_one() == 0
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts")).scalar_one() == 0

                class FailOnStartedAudit:
                    calls = 0

                    def append(self, tx, event):
                        self.calls += 1
                        if self.calls == 2:
                            raise RuntimeError("synthetic Audit failure")
                        return audit.append(tx, event)

                try:
                    build_service(FailOnStartedAudit()).submit(submit_command)
                except PlanVersionReviewSubmissionError:
                    pass
                else:
                    raise AssertionError("synthetic started Audit failure did not abort")
                with factory() as session:
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.rvw_reviews")).scalar_one() == 0
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.rvw_review_rounds")).scalar_one() == 0
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.pln_plan_version_review_state_results")).scalar_one() == 0
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.aud_events")).scalar_one() == 0
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts")).scalar_one() == 0

                service = build_service(audit)
                result = service.submit(submit_command)
                replay = service.submit(submit_command)
                assert replay == result
                with factory() as session:
                    state = session.get(PlanVersionRow, version)
                    assert state is not None and state.version_state == "IN_REVIEW"
                    assert state.review_ref == result.review_id
                    assert state.review_round_ref == result.round_id
                    event = session.query(PlanVersionReviewStateResultRow).filter_by(
                        plan_version_id=version, event_type="START").one()
                    assert event.actor_id == actor
                    assert event.review_id == result.review_id
                    assert event.review_round_id == result.round_id
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.rvw_reviews WHERE review_id=:id"),
                        {"id": result.review_id}).scalar_one() == 1
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.rvw_review_rounds WHERE review_round_id=:id"),
                        {"id": result.round_id}).scalar_one() == 1
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.rvw_round_events "
                        "WHERE review_round_id=:id AND event_type='STARTED'"),
                        {"id": result.round_id}).scalar_one() == 1
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.aud_events "
                        "WHERE target_object_id IN (:review,:round)"),
                        {"review": result.review_id, "round": result.round_id}).scalar_one() == 2
                    assert session.execute(text(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_PLAN_VERSION_SUBMIT_REVIEW'"),
                        {}).scalar_one() == 1
                assert evaluator.evaluate_snapshot_in_transaction.call_count == 3
                print("PLAN_VERSION_SUBMIT_REVIEW_PG_PASS: rejected-proof and started-Audit "
                      "failures rolled back; real Review/Round/START event, PlanVersion 0190 "
                      "result, two Audits, same-tx Receipt and exact replay; "
                      "current evaluator/session/license/project/reviewer decisions use test doubles")
            finally:
                engine.dispose()
        finally:
            if created:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (db_name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    main(parser.parse_args().port)
