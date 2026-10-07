"""Windows 11/PostgreSQL 18 proof for atomic Requirement Review submission."""

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
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
from plm_assistant.modules.capability.infrastructure.requirement_source_proof import SqlAlchemyCapabilityRequirementSourceProof
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import SqlAlchemyEvidenceRequirementSourceProof
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.api.submit_review import create_requirement_review_submission_router
from plm_assistant.modules.requirement.application.create_identity import CreateRequirementIdentity, RequirementIdentityCreateService
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, RequirementAcceptanceDraft,
    RequirementAssessmentEvidenceDraft, RequirementCapabilityAssessmentDraft,
    RequirementSourceDraft, RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.application.review_subject import RequirementReviewSubjectOwner
from plm_assistant.modules.requirement.application.submit_review import RequirementReviewSubmissionService
from plm_assistant.modules.requirement.application.validate_version import RequirementVersionCurrentValidator
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.review_subject_repository import SqlAlchemyRequirementReviewSubjectRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository
from plm_assistant.modules.review.application.project_persistence import ProjectReviewPersistenceService
from plm_assistant.modules.review.infrastructure.create_repository import SqlAlchemyReviewCreationRepository
from plm_assistant.modules.review.infrastructure.project_submission_repository import SqlAlchemyProjectReviewSubmissionRepository
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository


ROOT = Path(__file__).resolve().parents[2]
base = runpy.run_path(str(
    ROOT / "validation" / "req-01-a08-a02-p02-review-owner" / "verify.py"
))
connect, seed_dependencies = base["connect"], base["seed_dependencies"]
seed_user, insert_evidence = base["seed_user"], base["insert_evidence"]
CSRF = base["CSRF"]
TOKENS = {"pm": b"p" * 32, "impl": b"i" * 32}


class Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token not in TOKENS.values()
                or require_csrf and csrf_token != CSRF):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers(name="pm", *, key):
    return {
        "origin": "https://plm.example.test",
        "cookie": "plm_session=" + TOKENS[name].hex(),
        "x-csrf-token": CSRF.hex(), "idempotency-key": key,
    }


def expect(response, status):
    if response.status_code != status:
        raise AssertionError((status, response.status_code, response.text))
    return response


def main() -> None:
    database = "req01a10a06_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
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
            pm = seed_user(db, "A06 PM", "NONE", TOKENS["pm"])
            impl = seed_user(db, "A06 Implementer", "NONE", TOKENS["impl"])
            reviewer = seed_user(db, "A06 Reviewer", "NONE", b"r" * 32)
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
                    "'ELIGIBLE','A06 fixture',%s)",
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
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        receipts = SqlAlchemyIdempotencyReceipts()
        audit = AuditService(SqlAlchemyAuditRepository())
        common = dict(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, receipts=receipts, audit=audit,
            clock=lambda: now,
        )
        root = RequirementIdentityCreateService(
            **common, repository=SqlAlchemyRequirementIdentityCreateRepository(),
        ).create_requirement(CreateRequirementIdentity(
            TOKENS["pm"], CSRF, uuid.uuid4(), ids["project"], "REQ-A06",
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
            TOKENS["impl"], CSRF, uuid.uuid4(), ids["project"],
            root.requirement_id, 0, True, None, "A06 requirement",
            "Validated statement", "Business rationale", "PLM", "HIGH",
            "MEDIUM", "STANDARD_FUNCTION",
            (RequirementSourceDraft(
                "PROJECT_EVIDENCE", project_evidence, None,
                (project_evidence,)),),
            (RequirementAcceptanceDraft(
                "Observable result", "Execute acceptance test", "Project data",
                "Windows 11", "Signed report"),),
            (RequirementCapabilityAssessmentDraft(
                ids["baseline_version"], ids["capability_item"], "DIRECT",
                "Covered", "Use standard configuration", "HUMAN", "CONFIRMED",
                (RequirementAssessmentEvidenceDraft(
                    standard_evidence, "STANDARD"),
                 RequirementAssessmentEvidenceDraft(
                     project_evidence, "PROJECT")),
            ),), (), (), (), (), "Create A06 fixture", str(uuid.uuid4()),
        ))
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        owner = RequirementReviewSubjectOwner(
            repository=SqlAlchemyRequirementReviewSubjectRepository(),
            reviewers=reviewers,
            current=RequirementVersionCurrentValidator(
                survey_sources=object(), handover_sources=object(),
                human_decisions=object(), project_evidence=project_sources,
                capability_sources=capability_sources,
                fixed_evidence=fixed_evidence,
            ), audit=audit, clock=lambda: now,
        )
        service = RequirementReviewSubmissionService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=owner, clock=lambda: now,
            ), subjects=owner, clock=lambda: now,
        )
        router = create_requirement_review_submission_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            submissions=service,
        )
        path = (
            f"/api/v1/projects/{ids['project']}/requirements/"
            f"{root.requirement_id}/versions/"
            f"{created.requirement_version_id}:submit-review"
        )
        key = str(uuid.uuid4())
        body = {
            "reviewer_ids": [str(reviewer)],
            "policy_ref": "REQUIREMENT_ALL_V1",
            "due_at": None, "submission_note": None,
        }
        with TestClient(create_app(
            requirement_review_submission_router=router,
        ), base_url="https://plm.example.test") as client:
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                    "eligibility_reason='A06 current drift' WHERE evidence_id=%s",
                    (project_evidence,),
                )
            expect(client.post(
                path, headers=headers(key=key), json=body,
            ), 422)
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.rvw_reviews WHERE subject_id=%s",
                    (root.requirement_id,),
                ).fetchone()[0] == 0
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                    "eligibility_reason='A06 restored' WHERE evidence_id=%s",
                    (project_evidence,),
                )
            first = expect(client.post(
                path, headers=headers(key=key), json=body,
            ), 201).json()["data"]
            replay = expect(client.post(
                path, headers=headers(key=key), json=body,
            ), 201).json()["data"]
            assert first["review_id"] == replay["review_id"]
            assert first["review_round_id"] == replay["review_round_id"]
            conflict = {**body, "reviewer_ids": [str(pm), str(reviewer)]}
            expect(client.post(
                path, headers=headers(key=key), json=conflict,
            ), 409)
            expect(client.post(
                path, headers=headers("impl", key=str(uuid.uuid4())), json=body,
            ), 404)
            guard.denied = True
            expect(client.post(
                path, headers=headers(key=str(uuid.uuid4())), json=body,
            ), 403)
            guard.denied = False
        with connect(database) as db:
            counts = db.execute(
                "SELECT (SELECT count(*) FROM plm.rvw_reviews WHERE subject_id=%s),"
                "(SELECT count(*) FROM plm.rvw_review_rounds r JOIN plm.rvw_reviews v "
                "ON v.review_id=r.review_id WHERE v.subject_id=%s),"
                "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation=%s)",
                (root.requirement_id, root.requirement_id,
                 "V1_REQ_VERSION_SUBMIT_REVIEW"),
            ).fetchone()
            assert counts == (1, 1, 1), counts
            state = db.execute(
                "SELECT version_state,review_ref,review_round_ref FROM "
                "plm.req_requirement_versions WHERE requirement_version_id=%s",
                (created.requirement_version_id,),
            ).fetchone()
            assert state[0] == "IN_REVIEW" and all(state[1:]), state
            actions = db.execute(
                "SELECT action FROM plm.aud_events WHERE target_object_type='RVW-01' "
                "AND target_object_id=%s",
                (uuid.UUID(first["review_id"]),),
            ).fetchall()
            assert actions, actions
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(sql.Identifier(database)))
    print(
        "REQ_01_A10_A06_SUBMIT_REVIEW_PASS: current-fact revalidation, "
        "atomic Review create/start/bind/receipt/Audit, replay/conflict, role, "
        "License and drift verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
