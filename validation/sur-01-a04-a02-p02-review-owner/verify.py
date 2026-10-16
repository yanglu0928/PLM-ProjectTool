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
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
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
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.project_submission_repository import (
    SqlAlchemyProjectReviewSubmissionRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.survey.application.create_version import (
    CreateSurveyVersion, SurveyVersionCreateService,
)
from plm_assistant.modules.survey.application.review_subject import (
    SurveyReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.submit_review import (
    SubmitSurveyVersionReview, SurveyReviewSubmissionError,
    SurveyReviewSubmissionService,
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


def main(*, use_http: bool = False,
         submission_validation: bool = False) -> None:
    prefix = "sur01a05a05_" if submission_validation else (
        "sur01a04p04_" if use_http else "sur01a04p02_"
    )
    database = prefix + uuid.uuid4().hex[:6]
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
            target_department = db.execute("""
                INSERT INTO plm.prj_departments(
                  project_id,department_code,department_code_normalized,name)
                VALUES (%s,'SURVEY_TARGET','survey_target','Survey Target')
                RETURNING department_id
            """, (ids["project"],)).fetchone()[0]
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
                0, valid_questions(ids), (target_department,),
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
            receipts = SqlAlchemyIdempotencyReceipts()
            submission_service = None
            submission_replays = {}
            if submission_validation:
                submission_service = SurveyReviewSubmissionService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                    authorization=authorization, reviewers=reviewer_service,
                    receipts=receipts,
                    replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
                    reviews=ProjectReviewPersistenceService(
                        creation_repository=SqlAlchemyReviewCreationRepository(),
                        round_repository=SqlAlchemyReviewStartRepository(),
                        audit=audit, subjects=owner, clock=lambda: now,
                    ),
                    subjects=owner, clock=lambda: now,
                )

                class FailingAudit:
                    @staticmethod
                    def append(*args, **kwargs):
                        raise RuntimeError("synthetic review audit failure")

                failing = SurveyReviewSubmissionService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                    authorization=authorization, reviewers=reviewer_service,
                    receipts=receipts,
                    replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
                    reviews=ProjectReviewPersistenceService(
                        creation_repository=SqlAlchemyReviewCreationRepository(),
                        round_repository=SqlAlchemyReviewStartRepository(),
                        audit=FailingAudit(), subjects=owner, clock=lambda: now,
                    ),
                    subjects=owner, clock=lambda: now,
                )
                failed_command = SubmitSurveyVersionReview(
                    manager_token, CSRF, uuid.uuid4(), ids["project"],
                    survey_id, first.survey_version_id, (reviewer,),
                    "SURVEY_ALL_V1", str(uuid.uuid4()),
                )
                try:
                    failing.submit(failed_command)
                    raise AssertionError("audit failure must roll back submission")
                except SurveyReviewSubmissionError as exc:
                    assert exc.code == "SYSTEM_UNAVAILABLE", exc.code
                with connect(database) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.rvw_reviews WHERE "
                        "project_id=%s AND subject_id=%s",
                        (ids["project"], survey_id),
                    ).fetchone()[0] == 0
                    assert db.execute(
                        "SELECT version_state FROM plm.srv_survey_versions "
                        "WHERE survey_version_id=%s",
                        (first.survey_version_id,),
                    ).fetchone()[0] == "DRAFT"
            authorized = None
            with runtime.unit_of_work() as tx:
                authorized = owner.authorize_create(
                    tx, user_id=manager, project_id=ids["project"],
                    subject_type="SRV-02", subject_id=survey_id,
                    subject_version_id=first.survey_version_id,
                )
            assert authorized is not None
            assert authorized.policy_code == "SURVEY_ALL_V1"

            client = None
            if use_http:
                from fastapi.testclient import TestClient
                from plm_assistant.entrypoints.api import create_app
                from plm_assistant.entrypoints.windows_project_review import (
                    create_windows_project_review_router,
                )
                from plm_assistant.modules.auth.api.login_origin_policy import (
                    LoginOriginPolicy,
                )

                class Sessions:
                    @staticmethod
                    def validate(token, *, csrf_token=None, require_csrf=False):
                        assert token in (manager_token, b"r" * 32)
                        if require_csrf:
                            assert csrf_token == CSRF
                        return object()

                router = create_windows_project_review_router(
                    runtime, sessions=Sessions(),
                    origins=LoginOriginPolicy(["http://localhost"]),
                    license_guard=guard, audit=audit,
                )
                submission_router = None
                if submission_validation:
                    from plm_assistant.modules.survey.api.submit_review import (
                        create_survey_review_submission_router,
                    )
                    submission_router = create_survey_review_submission_router(
                        sessions=Sessions(),
                        origins=LoginOriginPolicy(["http://localhost"]),
                        submissions=submission_service,
                    )
                client = TestClient(
                    create_app(
                        review_command_router=router,
                        survey_review_submission_router=submission_router,
                    ),
                    base_url="http://localhost",
                )

            def headers(token: bytes, *, etag: str | None = None):
                result = {
                    "origin": "http://localhost",
                    "cookie": "plm_session=" + token.hex(),
                    "x-csrf-token": CSRF.hex(),
                    "idempotency-key": str(uuid.uuid4()),
                }
                if etag is not None:
                    result["if-match"] = etag
                return result

            def create_start(version_id):
                if submission_validation:
                    key = str(uuid.uuid4())
                    if client is not None:
                        path = (
                            f"/api/v1/projects/{ids['project']}/surveys/"
                            f"{survey_id}/versions/{version_id}:submit-review"
                        )
                        request_headers = headers(manager_token)
                        request_headers["idempotency-key"] = key
                        request_body = {
                            "reviewer_ids": [str(reviewer)],
                            "policy_ref": "SURVEY_ALL_V1",
                            "due_at": None, "submission_note": None,
                        }
                        submitted = client.post(
                            path, headers=request_headers, json=request_body,
                        )
                        assert submitted.status_code == 201, submitted.text
                        replayed = client.post(
                            path, headers=request_headers, json=request_body,
                        )
                        assert replayed.status_code == 201, replayed.text
                        assert replayed.json()["data"] == submitted.json()["data"]
                        submission_replays[version_id] = (
                            path, request_headers, request_body,
                        )
                        data = submitted.json()["data"]
                        return uuid.UUID(data["review_id"]), uuid.UUID(
                            data["review_round_id"]
                        )
                    assert submission_service is not None
                    command_value = SubmitSurveyVersionReview(
                        manager_token, CSRF, uuid.uuid4(), ids["project"],
                        survey_id, version_id, (reviewer,),
                        "SURVEY_ALL_V1", key,
                    )
                    submitted = submission_service.submit(command_value)
                    assert submission_service.submit(command_value) == submitted
                    submission_replays[version_id] = command_value
                    return submitted.review_id, submitted.round_id
                assert client is not None
                root = f"/api/v1/projects/{ids['project']}/reviews"
                created = client.post(root, headers=headers(manager_token), json={
                    "subject_ref": {
                        "resource_type": "SRV-02",
                        "resource_id": str(survey_id),
                        "version_id": str(version_id),
                    },
                })
                assert created.status_code == 201, created.text
                review_id = uuid.UUID(created.json()["data"]["review_id"])
                started = client.post(
                    f"{root}/{review_id}/rounds",
                    headers=headers(manager_token, etag='"v0"'),
                    json={
                        "subject_version_ref": str(version_id),
                        "reviewer_user_ids": [str(reviewer)],
                        "policy_code": "SURVEY_ALL_V1",
                    },
                )
                assert started.status_code == 201, started.text
                return review_id, uuid.UUID(
                    started.json()["data"]["review_round_id"]
                )

            review1, round1 = (
                create_start(first.survey_version_id) if client is not None
                else (uuid.uuid4(), uuid.uuid4())
            )
            identity1 = ReviewIdentitySnapshot(
                review1, "PROJECT", ids["project"], "SRV-02", survey_id,
                "SURVEY_ALL_V1", "DRAFT", None, 0,
            )
            request1 = ReviewSubjectStartRequest(
                manager, identity1, round1, first.survey_version_id,
                (reviewer,),
            )
            if client is None:
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
                    "WHERE department_id=%s", (target_department,),
                )
            if client is None:
                try:
                    with runtime.unit_of_work() as tx:
                        owner.require_transition_access_in_transaction(tx, approval)
                except ReviewSubjectAccessDenied:
                    pass
                else:
                    raise AssertionError("stale target department approved")
            else:
                stale_path = (
                    f"/api/v1/projects/{ids['project']}/reviews/{review1}/"
                    f"rounds/{round1}:decide"
                )
                stale = client.post(
                    stale_path, headers=headers(b"r" * 32),
                    json={"decision": "APPROVE", "comment": None},
                )
                assert stale.status_code == 404, stale.text
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.prj_departments SET state='ACTIVE' "
                    "WHERE department_id=%s", (target_department,),
                )

            if client is None:
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
            else:
                approve_headers = headers(b"r" * 32)
                approve_body = {"decision": "APPROVE", "comment": None}
                approve_path = (
                    f"/api/v1/projects/{ids['project']}/reviews/{review1}/"
                    f"rounds/{round1}:decide"
                )
                approved = client.post(
                    approve_path, headers=approve_headers, json=approve_body,
                )
                assert approved.status_code == 200, approved.text
                assert approved.json()["data"]["state"] == "APPROVED"
                replayed = client.post(
                    approve_path, headers=approve_headers, json=approve_body,
                )
                assert replayed.status_code == 200, replayed.text
                assert replayed.json()["data"] == approved.json()["data"]

            if submission_validation:
                replay = submission_replays[first.survey_version_id]
                if client is not None:
                    path, request_headers, request_body = replay
                    original = client.post(
                        path, headers=request_headers, json=request_body,
                    )
                    assert original.status_code == 201, original.text
                    assert uuid.UUID(original.json()["data"]["review_id"]) == review1
                    assert uuid.UUID(
                        original.json()["data"]["review_round_id"]
                    ) == round1
                else:
                    assert submission_service is not None
                    original = submission_service.submit(replay)
                    assert (original.review_id, original.round_id) == (review1, round1)

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
                (target_department,), str(uuid.uuid4()),
            ))
            review2, round2 = (
                create_start(second.survey_version_id) if client is not None
                else (uuid.uuid4(), uuid.uuid4())
            )
            identity2 = ReviewIdentitySnapshot(
                review2, "PROJECT", ids["project"], "SRV-02", survey_id,
                "SURVEY_ALL_V1", "DRAFT", None, 0,
            )
            request2 = ReviewSubjectStartRequest(
                manager, identity2, round2, second.survey_version_id,
                (reviewer,),
            )
            if client is None:
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
                    "WHERE department_id=%s", (target_department,),
                )
            if client is None:
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
            else:
                withdraw_headers = headers(manager_token, etag='"v1"')
                withdraw_body = {"reason": "Source changed"}
                withdraw_path = (
                    f"/api/v1/projects/{ids['project']}/reviews/{review2}/"
                    f"rounds/{round2}:withdraw"
                )
                response = client.post(
                    withdraw_path, headers=withdraw_headers, json=withdraw_body,
                )
                assert response.status_code == 200, response.text
                assert response.json()["data"]["state"] == "WITHDRAWN"
                replayed = client.post(
                    withdraw_path, headers=withdraw_headers, json=withdraw_body,
                )
                assert replayed.status_code == 200, replayed.text
                assert replayed.json()["data"] == response.json()["data"]

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
            if client is not None:
                client.close()
            marker = (
                "SUR_01_A05_A05_SUBMIT_REVIEW_PASS"
                if submission_validation else
                "SUR_01_A04_A02_P04_WINDOWS_HTTP_PASS" if use_http else
                "SUR_01_A04_A02_P02_REVIEW_OWNER_PASS"
            )
            print(
                marker + ": latest Draft creation "
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
