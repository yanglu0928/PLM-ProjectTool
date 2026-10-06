"""Windows 11/PostgreSQL 18 proof for the Survey Review Subject Owner."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.capability.infrastructure.survey_source_proof import (
    SqlAlchemyCapabilitySurveySourceProof,
)
from plm_assistant.modules.document.infrastructure.survey_template_proof import (
    SqlAlchemySurveyTemplateProof,
)
from plm_assistant.modules.handover.infrastructure.survey_source_proof import (
    SqlAlchemyHandoverSurveySourceProof,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.project.infrastructure.survey_source_proof import (
    SqlAlchemySurveyTargetDepartmentProof,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
    ReviewWithdrawalSnapshot,
)
from plm_assistant.modules.survey.application.create_version import (
    CreateSurveyVersion, SurveyVersionCreateService,
)
from plm_assistant.modules.survey.application.review_subject import (
    SurveyReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionCurrentValidator,
)
from plm_assistant.modules.survey.infrastructure.review_subject_repository import (
    SqlAlchemySurveyReviewSubjectRepository,
)
from plm_assistant.modules.survey.infrastructure.version_create_repository import (
    SqlAlchemySurveyVersionCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(
    str(ROOT / "validation/sur-01-a02-definition-schema/verify.py")
)
validation = runpy.run_path(
    str(ROOT / "validation/sur-01-a03-p03-version-validate/verify.py")
)
connect, seed_dependencies = schema["connect"], schema["seed_dependencies"]
seed_user, Guard, CSRF = (
    validation["seed_user"], validation["Guard"], validation["CSRF"],
)
valid_questions = validation["valid_questions"]


def fixed_round(*, now, review_id, round_id, project_id, survey_id,
                version_id, actor_id, reviewer_id, fingerprint):
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project_id, "SRV-02", survey_id,
        "SURVEY_ALL_V1", "IN_REVIEW", round_id, 1,
    )
    progress = ReviewRoundProgress(round_id, now, (reviewer_id,))
    fixed = FixedReviewRoundSnapshot(
        identity, 1, version_id, actor_id, progress, (uuid.uuid4(),), 0,
        uuid.uuid4(), fingerprint, 1, now, (), uuid.uuid4(), now, None,
    )
    return fixed, progress


def main() -> None:
    database = "sur01a04p02_" + uuid.uuid4().hex[:6]
    manager_token = b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database)
        ))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin",
            host="127.0.0.1", port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            manager = seed_user(db, "Survey Review Manager", "NONE", manager_token)
            reviewer = seed_user(db, "Survey Review Customer", "NONE", b"r" * 32)
            db.execute("""
                INSERT INTO plm.prj_project_members(
                  project_id,user_id,department_id,project_role)
                VALUES (%s,%s,%s,'PROJECT_MANAGER'),
                       (%s,%s,%s,'CUSTOMER_MANAGER')
            """, (ids["project"], manager, ids["department"],
                    ids["project"], reviewer, ids["department"]))
            survey_id = db.execute("""
                INSERT INTO plm.srv_surveys(project_id,name,created_by)
                VALUES (%s,'Review survey',%s) RETURNING survey_id
            """, (ids["project"], manager)).fetchone()[0]

        runtime = create_database_runtime(url)
        try:
            now = datetime.now(timezone.utc)
            guard = Guard()
            audit = AuditService(SqlAlchemyAuditRepository())
            project_repository = SqlAlchemyProjectAuthorizationRepository()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=project_repository,
            )
            sources = dict(
                handover_sources=SqlAlchemyHandoverSurveySourceProof(),
                capability_sources=SqlAlchemyCapabilitySurveySourceProof(),
                template_sources=SqlAlchemySurveyTemplateProof(),
                departments=SqlAlchemySurveyTargetDepartmentProof(),
            )
            creator = SurveyVersionCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization, **sources,
                repository=SqlAlchemySurveyVersionCreateRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                clock=lambda: now,
            )
            first = creator.create(CreateSurveyVersion(
                manager_token, CSRF, uuid.uuid4(), ids["project"], survey_id,
                0, valid_questions(ids), (ids["department"],),
                str(uuid.uuid4()),
            ))
            reviewer_service = ProjectReviewerQualificationService(
                users=SqlAlchemyReviewUserAccess(), projects=project_repository,
            )
            owner = SurveyReviewSubjectOwner(
                repository=SqlAlchemySurveyReviewSubjectRepository(),
                reviewers=reviewer_service,
                current=SurveyVersionCurrentValidator(**sources),
                audit=audit, clock=lambda: now,
            )
            authorized = None
            with runtime.unit_of_work() as tx:
                authorized = owner.authorize_create(
                    tx, user_id=manager, project_id=ids["project"],
                    subject_type="SRV-02", subject_id=survey_id,
                    subject_version_id=first.survey_version_id,
                )
            assert authorized is not None
            assert authorized.policy_code == "SURVEY_ALL_V1"

            review1, round1 = uuid.uuid4(), uuid.uuid4()
            identity1 = ReviewIdentitySnapshot(
                review1, "PROJECT", ids["project"], "SRV-02", survey_id,
                "SURVEY_ALL_V1", "DRAFT", None, 0,
            )
            request1 = ReviewSubjectStartRequest(
                manager, identity1, round1, first.survey_version_id,
                (reviewer,),
            )
            with runtime.unit_of_work() as tx:
                prepared = owner.prepare_start_in_transaction(tx, request1)
                assert prepared.basis == ()
                tx.session.execute(text("SET LOCAL session_replication_role='replica'"))
                tx.session.execute(text("""
                    INSERT INTO plm.rvw_reviews(
                      review_id,scope,project_id,subject_type,subject_id,
                      policy_code,review_state,active_round_id,lock_version,created_by)
                    VALUES (:review,'PROJECT',:project,'SRV-02',:survey,
                      'SURVEY_ALL_V1','IN_REVIEW',:round,1,:actor)
                """), {"review": review1, "project": ids["project"],
                        "survey": survey_id, "round": round1, "actor": manager})
                tx.session.execute(text("""
                    INSERT INTO plm.rvw_review_rounds(
                      review_round_id,review_id,scope,project_id,round_no,
                      subject_version_id,round_state,lock_version,started_by,started_at)
                    VALUES (:round,:review,'PROJECT',:project,1,:version,
                      'IN_REVIEW',0,:actor,:started)
                """), {"round": round1, "review": review1,
                        "project": ids["project"],
                        "version": first.survey_version_id,
                        "actor": manager, "started": now})
                tx.session.execute(text("SET LOCAL session_replication_role='origin'"))
                owner.finalize_start_in_transaction(tx, request1)
                owner.assert_active_lock_in_transaction(tx, request1)
                tx.commit()

            fixed1, progress1 = fixed_round(
                now=now, review_id=review1, round_id=round1,
                project_id=ids["project"], survey_id=survey_id,
                version_id=first.survey_version_id, actor_id=manager,
                reviewer_id=reviewer, fingerprint=first.content_fingerprint,
            )
            decision = ReviewDecisionSnapshot(
                uuid.uuid4(), round1, reviewer,
                ReviewDecisionKind.APPROVE, now,
            )
            approval = ReviewSubjectTransition(
                reviewer, uuid.uuid4(), fixed1,
                progress1.record_decision(decision), now,
            )
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.prj_departments SET state='INACTIVE' "
                    "WHERE department_id=%s", (ids["department"],),
                )
            try:
                with runtime.unit_of_work() as tx:
                    owner.require_transition_access_in_transaction(tx, approval)
            except ReviewSubjectAccessDenied:
                pass
            else:
                raise AssertionError("stale target department approved")
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.prj_departments SET state='ACTIVE' "
                    "WHERE department_id=%s", (ids["department"],),
                )

            with runtime.unit_of_work() as tx:
                owner.require_transition_access_in_transaction(tx, approval)
                tx.session.execute(text("SET LOCAL session_replication_role='replica'"))
                tx.session.execute(text(
                    "UPDATE plm.rvw_reviews SET review_state='APPROVED',"
                    "active_round_id=NULL,lock_version=2 WHERE review_id=:review"
                ), {"review": review1})
                tx.session.execute(text(
                    "UPDATE plm.rvw_review_rounds SET round_state='APPROVED',"
                    "lock_version=1 WHERE review_round_id=:round"
                ), {"round": round1})
                tx.session.execute(text("SET LOCAL session_replication_role='origin'"))
                owner.consume_terminal_in_transaction(tx, approval)
                owner.assert_terminal_consumed_in_transaction(tx, approval)
                tx.commit()

            with connect(database) as db:
                root = db.execute(
                    "SELECT current_approved_version_ref,lock_version "
                    "FROM plm.srv_surveys WHERE survey_id=%s", (survey_id,),
                ).fetchone()
                assert root[0] == first.survey_version_id
                second_expected_lock = root[1]
            second = creator.create(CreateSurveyVersion(
                manager_token, CSRF, uuid.uuid4(), ids["project"], survey_id,
                second_expected_lock, valid_questions(ids),
                (ids["department"],), str(uuid.uuid4()),
            ))
            review2, round2 = uuid.uuid4(), uuid.uuid4()
            identity2 = ReviewIdentitySnapshot(
                review2, "PROJECT", ids["project"], "SRV-02", survey_id,
                "SURVEY_ALL_V1", "DRAFT", None, 0,
            )
            request2 = ReviewSubjectStartRequest(
                manager, identity2, round2, second.survey_version_id,
                (reviewer,),
            )
            with runtime.unit_of_work() as tx:
                owner.prepare_start_in_transaction(tx, request2)
                tx.session.execute(text("SET LOCAL session_replication_role='replica'"))
                tx.session.execute(text("""
                    INSERT INTO plm.rvw_reviews(
                      review_id,scope,project_id,subject_type,subject_id,
                      policy_code,review_state,active_round_id,lock_version,created_by)
                    VALUES (:review,'PROJECT',:project,'SRV-02',:survey,
                      'SURVEY_ALL_V1','IN_REVIEW',:round,1,:actor)
                """), {"review": review2, "project": ids["project"],
                        "survey": survey_id, "round": round2, "actor": manager})
                tx.session.execute(text("""
                    INSERT INTO plm.rvw_review_rounds(
                      review_round_id,review_id,scope,project_id,round_no,
                      subject_version_id,round_state,lock_version,started_by,started_at)
                    VALUES (:round,:review,'PROJECT',:project,1,:version,
                      'IN_REVIEW',0,:actor,:started)
                """), {"round": round2, "review": review2,
                        "project": ids["project"],
                        "version": second.survey_version_id,
                        "actor": manager, "started": now})
                tx.session.execute(text("SET LOCAL session_replication_role='origin'"))
                owner.finalize_start_in_transaction(tx, request2)
                tx.commit()

            fixed2, progress2 = fixed_round(
                now=now, review_id=review2, round_id=round2,
                project_id=ids["project"], survey_id=survey_id,
                version_id=second.survey_version_id, actor_id=manager,
                reviewer_id=reviewer, fingerprint=second.content_fingerprint,
            )
            withdrawn = ReviewSubjectTransition(
                manager, uuid.uuid4(), fixed2,
                progress2.withdraw(ReviewWithdrawalSnapshot(
                    manager, now, "Source changed",
                )), now,
            )
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.prj_departments SET state='INACTIVE' "
                    "WHERE department_id=%s", (ids["department"],),
                )
            with runtime.unit_of_work() as tx:
                owner.require_transition_access_in_transaction(tx, withdrawn)
                tx.session.execute(text("SET LOCAL session_replication_role='replica'"))
                tx.session.execute(text(
                    "UPDATE plm.rvw_reviews SET review_state='WITHDRAWN',"
                    "active_round_id=NULL,lock_version=2 WHERE review_id=:review"
                ), {"review": review2})
                tx.session.execute(text(
                    "UPDATE plm.rvw_review_rounds SET round_state='WITHDRAWN',"
                    "lock_version=1 WHERE review_round_id=:round"
                ), {"round": round2})
                tx.session.execute(text("SET LOCAL session_replication_role='origin'"))
                owner.consume_terminal_in_transaction(tx, withdrawn)
                owner.assert_terminal_consumed_in_transaction(tx, withdrawn)
                tx.commit()

            with connect(database) as db:
                rows = dict(db.execute(
                    "SELECT survey_version_id,version_state FROM "
                    "plm.srv_survey_versions WHERE survey_id=%s", (survey_id,),
                ).fetchall())
                assert rows == {
                    first.survey_version_id: "APPROVED",
                    second.survey_version_id: "RETURNED",
                }, rows
                assert db.execute(
                    "SELECT current_approved_version_ref FROM plm.srv_surveys "
                    "WHERE survey_id=%s", (survey_id,),
                ).fetchone()[0] == first.survey_version_id
                actions = dict(db.execute(
                    "SELECT action,count(*) FROM plm.aud_events WHERE action LIKE "
                    "'SURVEY_VERSION_%' GROUP BY action"
                ).fetchall())
                assert actions["SURVEY_VERSION_APPROVED"] == 1
                assert actions["SURVEY_VERSION_WITHDRAWN"] == 1
            print(
                "SUR_01_A04_A02_P02_REVIEW_OWNER_PASS: latest Draft creation "
                "authorization, current reviewer/source validation, exact start "
                "binding, stale-source approval rejection, atomic approval and "
                "stale-source withdrawal with retained approved pointer verified "
                "on PostgreSQL 18"
            )
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)
            ))


if __name__ == "__main__":
    main()
