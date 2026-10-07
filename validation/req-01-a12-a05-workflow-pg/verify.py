"""Windows 11/PostgreSQL 18.6 proof for Requirement aggregate Workflow."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    create_windows_workflow_checklist_qualification_router,
    create_windows_workflow_checklist_record_router,
    create_windows_workflow_stage_transition_router,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import (
    SqlAlchemyPasswordIssueAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.review_start_access import (
    SqlAlchemyReviewStartAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    ScryptPasswordHasher,
)
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.capability.infrastructure.requirement_source_proof import (
    SqlAlchemyCapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import (
    SqlAlchemyEvidenceRequirementSourceProof,
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
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, RequirementAcceptanceDraft,
    RequirementAssessmentEvidenceDraft, RequirementCapabilityAssessmentDraft,
    RequirementSourceDraft, RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.application.review_subject import (
    RequirementReviewSubjectOwner,
)
from plm_assistant.modules.requirement.application.submit_review import (
    RequirementReviewSubmissionService, SubmitRequirementVersionReview,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionCurrentValidator,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import (
    SqlAlchemyRequirementIdentityCreateRepository,
)
from plm_assistant.modules.requirement.infrastructure.review_subject_repository import (
    SqlAlchemyRequirementReviewSubjectRepository,
)
from plm_assistant.modules.requirement.infrastructure.version_create_repository import (
    SqlAlchemyRequirementVersionCreateRepository,
)
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectRegistry,
)
from plm_assistant.modules.review.application.transition_command import (
    DecideReviewRound, ReviewTransitionCommandService,
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


ROOT = Path(__file__).resolve().parents[2]
base = runpy.run_path(str(
    ROOT / "validation/req-01-a08-a02-p02-review-owner/verify.py"
))
workflow_fixture = runpy.run_path(str(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py"
))
connect, seed_dependencies = base["connect"], base["seed_dependencies"]
seed_user, insert_evidence = base["seed_user"], base["insert_evidence"]
Guard, CSRF = base["Guard"], base["CSRF"]
ORIGIN = "http://localhost"
ITEMS = ("REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE")


class UnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"Requirement qualification used {name}")


def main() -> None:
    database = "req01a12a05_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, reviewer_token = b"p" * 32, b"i" * 32, b"r" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database),
        ))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            pm = seed_user(db, "A05 PM", "NONE", pm_token)
            impl = seed_user(db, "A05 Implementer", "NONE", impl_token)
            reviewer = seed_user(db, "A05 Reviewer", "NONE", reviewer_token)
            for actor, role in (
                (pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                (reviewer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,"
                    "department_id,project_role) VALUES (%s,%s,%s,%s)",
                    (ids["project"], actor, ids["department"], role),
                )
            project_evidence, _, _, _ = insert_evidence(db, ids)
            standard_evidence = uuid.uuid4()
            cap_review, cap_round, cap_snapshot = (
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.evd_evidence_records(evidence_id,scope,"
                    "project_id,document_id,document_version_id,locator_type,"
                    "locator_schema_version,locator_payload,content_fingerprint,"
                    "display_label,eligibility_state,eligibility_reason,created_by) "
                    "VALUES (%s,'GLOBAL',NULL,%s,%s,'DOCUMENT',1,"
                    "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Standard evidence',"
                    "'ELIGIBLE','A05 fixture',%s)",
                    (standard_evidence, ids["template_document"],
                     ids["template_version"], b"standard".ljust(32, b"x"),
                     ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,"
                    "subject_type,subject_id,policy_code,review_state,active_round_id,"
                    "lock_version,created_by) VALUES (%s,'GLOBAL',NULL,'CAP-01',%s,"
                    "'DEPLOYMENT_ALL_V1','APPROVED',NULL,2,%s)",
                    (cap_review, ids["baseline"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,"
                    "project_id,round_no,subject_version_id,round_state,lock_version,"
                    "started_by,started_at) VALUES (%s,%s,'GLOBAL',NULL,1,%s,"
                    "'APPROVED',1,%s,statement_timestamp())",
                    (cap_round, cap_review, ids["baseline_version"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,"
                    "review_round_id,scope,project_id,subject_type,subject_id,"
                    "subject_version_id,content_fingerprint,proof_schema_version,"
                    "verified_at) VALUES (%s,%s,%s,'GLOBAL',NULL,'CAP-01',%s,%s,%s,"
                    "1,statement_timestamp())",
                    (cap_snapshot, cap_review, cap_round, ids["baseline"],
                     ids["baseline_version"], b"c" * 32),
                )
                db.execute(
                    "UPDATE plm.cap_baseline_versions SET review_ref=%s,"
                    "review_round_ref=%s WHERE baseline_version_id=%s",
                    (cap_review, cap_round, ids["baseline_version"]),
                )

        runtime = create_database_runtime(url)
        now = datetime.now(timezone.utc)
        guard = Guard()
        audit = AuditService(SqlAlchemyAuditRepository())
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        receipts = SqlAlchemyIdempotencyReceipts()
        common = dict(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, receipts=receipts,
            audit=audit, clock=lambda: now,
        )
        root = RequirementIdentityCreateService(
            **common, repository=SqlAlchemyRequirementIdentityCreateRepository(),
        ).create_requirement(CreateRequirementIdentity(
            pm_token, CSRF, uuid.uuid4(), ids["project"], "REQ-WORKFLOW-001",
            str(uuid.uuid4()),
        ))
        project_sources = SqlAlchemyEvidenceRequirementSourceProof()
        capability_sources = SqlAlchemyCapabilityRequirementSourceProof()
        fixed_evidence = SqlAlchemyEvidenceFixedSourceRepository()
        created = RequirementVersionCreateService(
            **common, repository=SqlAlchemyRequirementVersionCreateRepository(),
            survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=project_sources,
            capability_sources=capability_sources, fixed_evidence=fixed_evidence,
        ).create(CreateRequirementVersion(
            impl_token, CSRF, uuid.uuid4(), ids["project"],
            root.requirement_id, 0, True, None, "Workflow requirement",
            "Observable requirement statement", "Business rationale", "PLM",
            "HIGH", "MEDIUM", "STANDARD_FUNCTION",
            (RequirementSourceDraft(
                "PROJECT_EVIDENCE", project_evidence, None,
                (project_evidence,)),),
            (RequirementAcceptanceDraft(
                "Observable result", "Execute acceptance test", "Project data",
                "Windows 11", "Signed acceptance report"),),
            (RequirementCapabilityAssessmentDraft(
                ids["baseline_version"], ids["capability_item"], "DIRECT",
                "Covered", "Use standard configuration", "HUMAN", "CONFIRMED",
                (RequirementAssessmentEvidenceDraft(
                    standard_evidence, "STANDARD"),
                 RequirementAssessmentEvidenceDraft(
                    project_evidence, "PROJECT")),
            ),), (), (), (), (), "Create A05 fixture", str(uuid.uuid4()),
        ))
        current = RequirementVersionCurrentValidator(
            survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=project_sources,
            capability_sources=capability_sources,
            fixed_evidence=fixed_evidence,
        )
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        owner = RequirementReviewSubjectOwner(
            repository=SqlAlchemyRequirementReviewSubjectRepository(),
            reviewers=reviewers, current=current, audit=audit,
            clock=lambda: now,
        )
        submission = RequirementReviewSubmissionService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=owner, clock=lambda: now,
            ), subjects=owner, clock=lambda: now,
        ).submit(SubmitRequirementVersionReview(
            pm_token, CSRF, uuid.uuid4(), ids["project"], root.requirement_id,
            created.requirement_version_id, (reviewer,),
            "REQUIREMENT_ALL_V1", str(uuid.uuid4()),
        ))
        review_subjects = ProjectReviewSubjectRegistry((owner,))
        approved = ReviewTransitionCommandService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyReviewStartAccess(), projects=authorization,
            license_guard=guard, repository=SqlAlchemyReviewTransitionRepository(),
            receipts=receipts, audit=audit, subjects=review_subjects,
            clock=lambda: now,
        ).decide_idempotent(DecideReviewRound(
            reviewer_token, CSRF, ids["project"], submission.review_id,
            submission.round_id, uuid.uuid4(), ReviewDecisionKind.APPROVE,
        ), idempotency_key=str(uuid.uuid4()))
        assert approved.state.value == "APPROVED"

        with connect(database) as db, db.transaction():
            workflow_id = workflow_fixture["initialize"](
                db, ids["project"], pm,
            )
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',"
                "current_stage_key='REQUIREMENT',lock_version=7,"
                "updated_at=statement_timestamp() WHERE workflow_id=%s",
                (workflow_id,),
            )
            db.execute(
                "UPDATE plm.wfl_stages SET stage_state=CASE "
                "WHEN stage_key IN ('HANDOVER','SURVEY') THEN 'COMPLETED' "
                "WHEN stage_key='REQUIREMENT' THEN 'ACTIVE' ELSE 'NOT_STARTED' END "
                "WHERE workflow_id=%s", (workflow_id,),
            )
            db.execute(
                "UPDATE plm.wfl_checklist_items SET item_state='PASS',lock_version=1 "
                "WHERE workflow_id=%s AND (item_key LIKE 'HANDOVER_%%' "
                "OR item_key LIKE 'SURVEY_%%')", (workflow_id,),
            )

        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
            audit=audit, idempotency=receipts,
        )
        origins = LoginOriginPolicy([ORIGIN])
        unused = UnusedDependency()
        qualification_router = create_windows_workflow_checklist_qualification_router(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            documents=unused, downloads=unused, parse_results=unused,
        )
        record_router = create_windows_workflow_checklist_record_router(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, documents=unused, downloads=unused,
            parse_results=unused,
        )
        transition_router = create_windows_workflow_stage_transition_router(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, documents=unused, downloads=unused,
            parse_results=unused,
        )
        app = create_app(
            workflow_checklist_qualification_router=qualification_router,
            workflow_checklist_record_router=record_router,
            workflow_transition_router=transition_router,
        )
        cookie = "plm_session=" + pm_token.hex()
        get_headers = {"cookie": cookie, "host": "localhost"}
        write_headers = {
            "cookie": cookie, "x-csrf-token": CSRF.hex(), "origin": ORIGIN,
        }
        with TestClient(app, base_url=ORIGIN) as client:
            previews = {}
            for item in ITEMS:
                response = client.get(
                    f"/api/v1/projects/{ids['project']}/workflow/checklist-items/"
                    f"{item}/qualification", headers=get_headers,
                )
                assert response.status_code == 200, response.text
                value = response.json()["data"]
                assert value["stage_key"] == "REQUIREMENT"
                assert value["requirement_version_refs"] == [
                    str(created.requirement_version_id),
                ]
                assert value["review_round_refs"] == [str(submission.round_id)]
                assert value["evidence_refs"] == [str(project_evidence)]
                assert "survey_conclusion_id" not in value
                assert "review_round_ref" not in value
                previews[item] = value

            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.evd_evidence_records SET "
                    "eligibility_state='INELIGIBLE',eligibility_reason='A05 drift',"
                    "lock_version=lock_version+1 WHERE evidence_id=%s",
                    (project_evidence,),
                )
            drift = client.post(
                f"/api/v1/projects/{ids['project']}/workflow/checklist-items/"
                f"{ITEMS[0]}:record",
                headers={**write_headers, "idempotency-key": str(uuid.uuid4()),
                         "if-match": '"v7"'},
                json={
                    "result": "PASS", "reason": "Current facts verified",
                    "impact": "Validation only",
                    "evidence_refs": previews[ITEMS[0]]["evidence_refs"],
                    "exception_refs": [],
                },
            )
            assert drift.status_code == 409, drift.text
            assert drift.json()["error"]["code"] == "WORKFLOW_GATE_NOT_SATISFIED"
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.evd_evidence_records SET "
                    "eligibility_state='ELIGIBLE',eligibility_reason='A05 restored',"
                    "lock_version=lock_version+1 WHERE evidence_id=%s",
                    (project_evidence,),
                )

            etag = '"v7"'
            for item in ITEMS:
                response = client.post(
                    f"/api/v1/projects/{ids['project']}/workflow/checklist-items/"
                    f"{item}:record",
                    headers={**write_headers,
                             "idempotency-key": str(uuid.uuid4()),
                             "if-match": etag},
                    json={
                        "result": "PASS", "reason": "Current facts verified",
                        "impact": "Validation only",
                        "evidence_refs": previews[item]["evidence_refs"],
                        "exception_refs": [],
                    },
                )
                assert response.status_code == 200, response.text
                etag = response.headers["etag"]
            assert etag == '"v9"'

            transition_key = str(uuid.uuid4())
            transition_headers = {
                **write_headers, "idempotency-key": transition_key,
                "if-match": etag,
            }
            transition_body = {
                "target_stage_key": "PROTOTYPE",
                "reason": "Requirement aggregate accepted",
                "gate_snapshot_refs": [],
            }
            first = client.post(
                f"/api/v1/projects/{ids['project']}/workflow:transition",
                headers=transition_headers, json=transition_body,
            )
            assert first.status_code == 200, first.text
            assert first.json()["data"]["from_stage"] == "REQUIREMENT"
            assert first.json()["data"]["to_stage"] == "PROTOTYPE"
            assert first.headers["etag"] == '"v10"'
            replay = client.post(
                f"/api/v1/projects/{ids['project']}/workflow:transition",
                headers=transition_headers, json=transition_body,
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["data"] == first.json()["data"]

        with connect(database) as db:
            assert db.execute(
                "SELECT current_stage_key,lock_version FROM "
                "plm.wfl_project_workflows WHERE workflow_id=%s",
                (workflow_id,),
            ).fetchone() == ("PROTOTYPE", 10)
            assert db.execute(
                "SELECT count(*) FROM plm.wfl_checklist_records WHERE "
                "project_id=%s AND result='PASS'", (ids["project"],),
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.wfl_checklist_record_refs b JOIN "
                "plm.wfl_checklist_records r ON r.record_id=b.record_id "
                "WHERE r.project_id=%s AND "
                "b.ref_kind='REVIEW_ROUND' AND b.ref_id=%s",
                (ids["project"], submission.round_id),
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.wfl_stage_transitions WHERE project_id=%s "
                "AND from_stage='REQUIREMENT' AND to_stage='PROTOTYPE'",
                (ids["project"],),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
                "AND action='WORKFLOW_CHECKLIST_RECORDED'",
                (ids["project"],),
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
                "AND action='WORKFLOW_STAGE_TRANSITIONED'",
                (ids["project"],),
            ).fetchone()[0] == 1
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(sql.Identifier(database)))
    print(
        "REQ_01_A12_A05_WORKFLOW_PG_PASS: Windows 11/PostgreSQL 18.6 real "
        "Requirement source/capability/review qualification, aggregate preview, "
        "write-time drift rejection, two PASS records, REQUIREMENT->PROTOTYPE, "
        "Review basis, Audit/receipt/replay, Alembic drift and cleanup verified"
    )


if __name__ == "__main__":
    main()
