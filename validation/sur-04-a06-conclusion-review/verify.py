"""Windows 11/PostgreSQL 18 proof for SurveyConclusion Review lifecycle."""

from __future__ import annotations

import importlib.util
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
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
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
    ALL_MEMBERS, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectRegistry,
)
from plm_assistant.modules.review.application.transition_command import (
    DecideReviewRound, ReviewTransitionCommandError,
    ReviewTransitionCommandService,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.project_submission_repository import (
    SqlAlchemyProjectReviewSubmissionRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.review.infrastructure.transition_repository import (
    SqlAlchemyReviewTransitionRepository,
)
from plm_assistant.modules.survey.application.conclusion_review_subject import (
    SurveyConclusionReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordProof, SurveyConclusionProjectRecordProofService,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionEvidenceInput, CreateSurveyConclusion,
    DepartmentConclusionInput, SurveyConclusionCreateService,
)
from plm_assistant.modules.survey.application.submit_conclusion_review import (
    SubmitSurveyConclusionReview, SurveyConclusionReviewSubmissionError,
    SurveyConclusionReviewSubmissionService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionCurrentValidator,
)
from plm_assistant.modules.survey.infrastructure.conclusion_review_repository import (
    SqlAlchemySurveyConclusionReviewRepository,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a04 = load(
    ROOT / "validation" / "sur-04-a04-conclusion-create-read" / "verify.py",
    "sur04a06_fixture",
)
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
schema, definition, round_fixture = a04.schema, a04.definition, a04.round_fixture
seed_user = auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


class UnusedOwner:
    @staticmethod
    def prove(*args, **kwargs):
        return None


def expect_submit(code: str, action) -> None:
    try:
        action()
    except SurveyConclusionReviewSubmissionError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected submit failure: " + code)


def expect_transition(code: str, action) -> None:
    try:
        action()
    except ReviewTransitionCommandError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected transition failure: " + code)


def expect_database_error(expected: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("expected database failure: " + expected)


def fingerprint(
    *, project_id, survey_id, round_id, department_id, evidence_id,
    document_id, document_version_id, evidence_fingerprint, supersedes,
    title,
):
    department = DepartmentConclusionInput(
        department_id, title, "Reviewable conclusion " + title, (),
    )
    command_value = CreateSurveyConclusion(
        b"x" * 32, b"x" * 32, uuid.uuid4(), project_id, survey_id,
        (round_id,), (department,), (),
        (ConclusionEvidenceInput(evidence_id, "SUPPORT"),), (), (),
        supersedes, "x" * 16,
    )
    proof = ConclusionProjectRecordProof(
        evidence_id, project_id, document_id, document_version_id, 0,
        evidence_fingerprint, uuid.uuid4(),
    )
    return department, canonical_payload_fingerprint(
        SurveyConclusionCreateService._snapshot_payload(
            command_value, (), (proof,), (), (),
        ))


def main(approved_callback=None) -> None:
    database = "sur04a06_" + uuid.uuid4().hex[:8]
    manager_token, reviewer_token = b"m" * 32, b"r" * 32
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username=USER, host=HOST, port=PORT,
            database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        with schema.connect(database) as db:
            ids = definition.seed_dependencies(db)
            manager = seed_user(db, "Conclusion Review PM", "NONE", manager_token)
            reviewer = seed_user(
                db, "Conclusion Review Customer", "NONE", reviewer_token,
            )
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,"
                "department_id,project_role) VALUES "
                "(%s,%s,%s,'PROJECT_MANAGER'),"
                "(%s,%s,%s,'CUSTOMER_MANAGER')",
                (ids["project"], manager, ids["department"],
                 ids["project"], reviewer, ids["department"]),
            )
            survey, version = definition.insert_valid(
                db, ids, name="Conclusion Review survey",
            )
            round_fixture.approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,created_by) VALUES (%s,%s,%s,1,%s) "
                "RETURNING survey_round_id",
                (survey, version, ids["project"], manager),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s",
                (manager, manager, round_id),
            )
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                    "WHERE survey_round_id=%s",
                    (manager, b"c" * 32, manager, round_id),
                )
            evidence, document, document_version, evidence_fingerprint = (
                round_fixture.insert_evidence(db, ids)
            )

            series_id = uuid.uuid4()

            def insert_conclusion(version_no, title, supersedes=None):
                conclusion_id = uuid.uuid4()
                department, content = fingerprint(
                    project_id=ids["project"], survey_id=survey,
                    round_id=round_id, department_id=ids["department"],
                    evidence_id=evidence, document_id=document,
                    document_version_id=document_version,
                    evidence_fingerprint=evidence_fingerprint,
                    supersedes=supersedes, title=title,
                )
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.srv_conclusions(survey_conclusion_id,"
                    "conclusion_series_id,project_id,survey_id,round_refs,"
                    "ai_task_refs,version_no,content_fingerprint,"
                    "declared_department_count,declared_module_count,"
                    "declared_evidence_count,declared_open_issue_count,"
                    "supersedes_ref,created_by) VALUES "
                    "(%s,%s,%s,%s,ARRAY[%s]::uuid[],'{}'::uuid[],%s,%s,"
                    "1,0,1,0,%s,%s)",
                        (conclusion_id, series_id, ids["project"], survey,
                         round_id, version_no, content, supersedes, manager),
                    )
                    db.execute(
                        "INSERT INTO plm.srv_department_conclusions("
                    "survey_conclusion_id,conclusion_series_id,project_id,"
                    "department_id,title,statement,response_refs,ordinal) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'{}'::uuid[],0)",
                        (conclusion_id, series_id, ids["project"],
                         department.department_id, department.title,
                         department.statement),
                    )
                    db.execute(
                        "INSERT INTO plm.srv_conclusion_evidence_refs("
                    "survey_conclusion_id,conclusion_series_id,project_id,"
                    "reference_role,document_id,document_version_id,evidence_id,"
                    "observed_evidence_lock_version,content_fingerprint,ordinal) "
                    "VALUES (%s,%s,%s,'SUPPORT',%s,%s,%s,0,%s,0)",
                        (conclusion_id, series_id, ids["project"], document,
                         document_version, evidence, evidence_fingerprint),
                    )
                return conclusion_id

            first = insert_conclusion(1, "Version 1")

        runtime = create_database_runtime(url)
        now = datetime.now(timezone.utc)
        guard = Guard()
        guard.enabled = True
        audit = AuditService(SqlAlchemyAuditRepository())
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        reviewer_service = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", evidence_fingerprint.hex(),
        )
        evidence_owner = SurveyConclusionProjectRecordProofService(
            evidence=EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=project_repository,
                evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                documents=a04.a03.FixedDocument(facts),
                allowed_project_roles=ALL_MEMBERS,
                required_document_category="PROJECT_RECORD",
            ),
            allowed_verified_roles=ALL_MEMBERS,
        )
        current = SurveyConclusionCurrentValidator(
            response_owner=UnusedOwner(), evidence_owner=evidence_owner,
            issue_owner=UnusedOwner(), ai_owner=UnusedOwner(),
        )
        owner = SurveyConclusionReviewSubjectOwner(
            repository=SqlAlchemySurveyConclusionReviewRepository(),
            reviewers=reviewer_service, current=current, audit=audit,
            clock=lambda: now,
        )
        subjects = ProjectReviewSubjectRegistry((owner,))
        receipts = SqlAlchemyIdempotencyReceipts()

        def submit_service(audit_value=None):
            active_audit = audit_value or audit
            return SurveyConclusionReviewSubmissionService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization, reviewers=reviewer_service,
                receipts=receipts,
                replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
                reviews=ProjectReviewPersistenceService(
                    creation_repository=SqlAlchemyReviewCreationRepository(),
                    round_repository=SqlAlchemyReviewStartRepository(),
                    audit=active_audit, subjects=subjects, clock=lambda: now,
                ),
                subjects=subjects, clock=lambda: now,
            )

        def submit(conclusion_id, *, key=None, target=None):
            return (target or submit_service()).submit(
                SubmitSurveyConclusionReview(
                    manager_token, CSRF, uuid.uuid4(), ids["project"],
                    series_id, conclusion_id, (reviewer,),
                    "SURVEY_CONCLUSION_ALL_V1", key or str(uuid.uuid4()),
                ))

        rollback_key = str(uuid.uuid4())
        expect_submit("SYSTEM_UNAVAILABLE", lambda: submit(
            first, key=rollback_key, target=submit_service(FailedAudit()),
        ))
        first_review = submit(first, key=rollback_key)
        assert submit(first, key=rollback_key) == first_review

        transitions = ReviewTransitionCommandService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), projects=authorization,
            license_guard=guard,
            repository=SqlAlchemyReviewTransitionRepository(),
            receipts=receipts, audit=audit, subjects=subjects,
            clock=lambda: now,
        )

        def decide(submission, decision, *, key=None, comment=None):
            return transitions.decide_idempotent(
                DecideReviewRound(
                    reviewer_token, CSRF, ids["project"],
                    submission.review_id, submission.round_id, uuid.uuid4(),
                    decision, comment,
                ), idempotency_key=key or str(uuid.uuid4()),
            )

        with schema.connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',closed_by=NULL,"
                "closed_at=NULL,close_report_fingerprint=NULL "
                "WHERE survey_round_id=%s", (round_id,),
            )
        expect_transition("RESOURCE_NOT_FOUND", lambda: decide(
            first_review, ReviewDecisionKind.APPROVE,
        ))
        with schema.connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                "closed_at=statement_timestamp(),close_report_fingerprint=%s "
                "WHERE survey_round_id=%s",
                (manager, b"c" * 32, round_id),
            )
        approved_first = decide(first_review, ReviewDecisionKind.APPROVE)
        assert approved_first.state.value == "APPROVED"

        with schema.connect(database) as db, db.transaction():
            department, content = fingerprint(
                project_id=ids["project"], survey_id=survey,
                round_id=round_id, department_id=ids["department"],
                evidence_id=evidence, document_id=document,
                document_version_id=document_version,
                evidence_fingerprint=evidence_fingerprint,
                supersedes=first, title="Version 2",
            )
            second = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.srv_conclusions(survey_conclusion_id,"
                "conclusion_series_id,project_id,survey_id,round_refs,ai_task_refs,"
                "version_no,content_fingerprint,declared_department_count,"
                "declared_module_count,declared_evidence_count,"
                "declared_open_issue_count,supersedes_ref,created_by) VALUES "
                "(%s,%s,%s,%s,ARRAY[%s]::uuid[],'{}'::uuid[],2,%s,1,0,1,0,%s,%s)",
                (second, series_id, ids["project"], survey, round_id, content,
                 first, manager),
            )
            db.execute(
                "INSERT INTO plm.srv_department_conclusions("
                "survey_conclusion_id,conclusion_series_id,project_id,department_id,"
                "title,statement,response_refs,ordinal) VALUES "
                "(%s,%s,%s,%s,%s,%s,'{}'::uuid[],0)",
                (second, series_id, ids["project"], ids["department"],
                 department.title, department.statement),
            )
            db.execute(
                "INSERT INTO plm.srv_conclusion_evidence_refs("
                "survey_conclusion_id,conclusion_series_id,project_id,reference_role,"
                "document_id,document_version_id,evidence_id,"
                "observed_evidence_lock_version,content_fingerprint,ordinal) "
                "VALUES (%s,%s,%s,'SUPPORT',%s,%s,%s,0,%s,0)",
                (second, series_id, ids["project"], document, document_version,
                 evidence, evidence_fingerprint),
            )
        second_review = submit(second)
        returned = decide(
            second_review, ReviewDecisionKind.RETURN,
            comment="Clarify implementation boundary",
        )
        assert returned.state.value == "RETURNED"

        with schema.connect(database) as db, db.transaction():
            department, content = fingerprint(
                project_id=ids["project"], survey_id=survey,
                round_id=round_id, department_id=ids["department"],
                evidence_id=evidence, document_id=document,
                document_version_id=document_version,
                evidence_fingerprint=evidence_fingerprint,
                supersedes=second, title="Version 3",
            )
            third = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.srv_conclusions(survey_conclusion_id,"
                "conclusion_series_id,project_id,survey_id,round_refs,ai_task_refs,"
                "version_no,content_fingerprint,declared_department_count,"
                "declared_module_count,declared_evidence_count,"
                "declared_open_issue_count,supersedes_ref,created_by) VALUES "
                "(%s,%s,%s,%s,ARRAY[%s]::uuid[],'{}'::uuid[],3,%s,1,0,1,0,%s,%s)",
                (third, series_id, ids["project"], survey, round_id, content,
                 second, manager),
            )
            db.execute(
                "INSERT INTO plm.srv_department_conclusions("
                "survey_conclusion_id,conclusion_series_id,project_id,department_id,"
                "title,statement,response_refs,ordinal) VALUES "
                "(%s,%s,%s,%s,%s,%s,'{}'::uuid[],0)",
                (third, series_id, ids["project"], ids["department"],
                 department.title, department.statement),
            )
            db.execute(
                "INSERT INTO plm.srv_conclusion_evidence_refs("
                "survey_conclusion_id,conclusion_series_id,project_id,reference_role,"
                "document_id,document_version_id,evidence_id,"
                "observed_evidence_lock_version,content_fingerprint,ordinal) "
                "VALUES (%s,%s,%s,'SUPPORT',%s,%s,%s,0,%s,0)",
                (third, series_id, ids["project"], document, document_version,
                 evidence, evidence_fingerprint),
            )
        third_review = submit(third)
        assert decide(third_review, ReviewDecisionKind.APPROVE).state.value \
            == "APPROVED"

        if approved_callback is not None:
            approved_callback({
                "database": database,
                "runtime": runtime,
                "project_id": ids["project"],
                "department_id": ids["department"],
                "manager_id": manager,
                "manager_token": manager_token,
                "guard": guard,
                "audit": audit,
                "evidence_id": evidence,
                "document_id": document,
                "document_version_id": document_version,
                "evidence_fingerprint": evidence_fingerprint,
                "document_facts": facts,
                "survey_id": survey,
                "survey_conclusion_id": third,
                "conclusion_series_id": series_id,
                "review_id": third_review.review_id,
                "review_round_id": third_review.round_id,
            })

        with schema.connect(database) as db:
            states = db.execute(
                "SELECT version_no,conclusion_state FROM plm.srv_conclusions "
                "WHERE conclusion_series_id=%s ORDER BY version_no",
                (series_id,),
            ).fetchall()
            assert states == [(1, "SUPERSEDED"), (2, "RETURNED"),
                              (3, "APPROVED")], states
            assert db.execute(
                "SELECT count(*) FROM plm.rvw_subject_locks WHERE "
                "subject_type='SRV-05' AND subject_id=%s AND lock_state='ACTIVE'",
                (series_id,),
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action IN "
                "('SURVEY_CONCLUSION_APPROVED','SURVEY_CONCLUSION_RETURNED') "
                "AND target_object_id=%s", (series_id,),
            ).fetchone()[0] == 3
            leaked = db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE "
                "coalesce(reason_code,'') LIKE %s",
                ("%" + manager_token.hex() + "%",),
            ).fetchone()[0]
            assert leaked == 0
            expect_database_error(
                "Survey Conclusion payload is immutable",
                lambda: db.execute(
                    "UPDATE plm.srv_conclusions SET content_fingerprint=%s "
                    "WHERE survey_conclusion_id=%s", (b"z" * 32, third),
                ),
            )
            expect_database_error(
                "Survey Conclusion lifecycle transition is invalid",
                lambda: db.execute(
                    "UPDATE plm.srv_conclusions SET conclusion_state='APPROVED' "
                    "WHERE survey_conclusion_id=%s", (second,),
                ),
            )
        runtime.dispose()
        runtime = None
        command.downgrade(cfg, "20261007_0109")
        with schema.connect(database) as db:
            assert db.execute(
                "SELECT version_num FROM plm.alembic_version",
            ).fetchone()[0] == "20261007_0109"
            expect_database_error(
                "Survey Conclusion history is immutable",
                lambda: db.execute(
                    "UPDATE plm.srv_conclusions SET conclusion_state="
                    "'SUPERSEDED' WHERE survey_conclusion_id=%s", (third,),
                ),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with schema.connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database),
            ))
    print(
        "SUR_04_A06_CONCLUSION_REVIEW_PASS: transient proof context, atomic "
        "submission, approval-time source reproof, rollback/replay, RETURNED, "
        "replacement APPROVED/SUPERSEDED and released Review locks verified on "
        "Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
