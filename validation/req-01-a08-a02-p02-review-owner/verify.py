"""Windows 11/PostgreSQL 18 proof for Requirement Review Subject Owner."""

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
    RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
    RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.application.review_subject import (
    RequirementReviewSubjectOwner,
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
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation/ai-02-a02-model-create/verify.py")
)
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
definition = runpy.run_path(
    str(ROOT / "validation/sur-01-a02-definition-schema/verify.py")
)
rounds = runpy.run_path(
    str(ROOT / "validation/sur-02-a02-round-schema/verify.py")
)
seed_dependencies = definition["seed_dependencies"]
insert_evidence = rounds["insert_evidence"]


def fixed_round(*, now, review_id, round_id, project_id, requirement_id,
                version_id, actor_id, reviewer_id, fingerprint):
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project_id, "REQ-03", requirement_id,
        "REQUIREMENT_ALL_V1", "IN_REVIEW", round_id, 1,
    )
    progress = ReviewRoundProgress(round_id, now, (reviewer_id,))
    fixed = FixedReviewRoundSnapshot(
        identity, 1, version_id, actor_id, progress, (uuid.uuid4(),), 0,
        uuid.uuid4(), fingerprint, 1, now, (), uuid.uuid4(), now, None,
    )
    return fixed, progress


def main() -> None:
    database = "req01a08p02_" + uuid.uuid4().hex[:8]
    pm_token, impl_token = b"p" * 32, b"i" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database)
        ))
    runtime = None
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
            pm = seed_user(db, "Requirement Review PM", "NONE", pm_token)
            impl = seed_user(db, "Requirement Review Implementer", "NONE", impl_token)
            reviewer = seed_user(db, "Requirement Review Customer", "NONE", b"r" * 32)
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (impl, "IMPLEMENTATION_MEMBER"),
                                (reviewer, "CUSTOMER_MANAGER")):
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
                    "'ELIGIBLE','REQ-01-A08 fixture',%s)",
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
            unit_of_work=runtime.unit_of_work,
            repository=project_repository,
        )
        common = dict(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization,
            receipts=SqlAlchemyIdempotencyReceipts(), clock=lambda: now,
        )
        audit = AuditService(SqlAlchemyAuditRepository())
        root = RequirementIdentityCreateService(
            **common, repository=SqlAlchemyRequirementIdentityCreateRepository(),
            audit=audit,
        ).create_requirement(CreateRequirementIdentity(
            pm_token, CSRF, uuid.uuid4(), ids["project"], "REQ-REVIEW",
            str(uuid.uuid4()),
        ))
        project_sources = SqlAlchemyEvidenceRequirementSourceProof()
        capability_sources = SqlAlchemyCapabilityRequirementSourceProof()
        fixed_evidence = SqlAlchemyEvidenceFixedSourceRepository()
        creator = RequirementVersionCreateService(
            **common, repository=SqlAlchemyRequirementVersionCreateRepository(),
            audit=audit, survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=project_sources,
            capability_sources=capability_sources,
            fixed_evidence=fixed_evidence,
        )
        standard = (RequirementCapabilityAssessmentDraft(
            ids["baseline_version"], ids["capability_item"], "DIRECT",
            "Standard capability covers requirement", "Use standard configuration",
            "HUMAN", "CONFIRMED",
            (RequirementAssessmentEvidenceDraft(standard_evidence, "STANDARD"),
             RequirementAssessmentEvidenceDraft(project_evidence, "PROJECT")),
        ),)

        def root_lock():
            with connect(database) as db:
                return db.execute(
                    "SELECT lock_version FROM plm.req_requirements WHERE "
                    "requirement_id=%s", (root.requirement_id,),
                ).fetchone()[0]

        def create_version(base):
            return creator.create(CreateRequirementVersion(
                impl_token, CSRF, uuid.uuid4(), ids["project"],
                root.requirement_id, root_lock(), base is None, base, None,
                "Validated requirement", "Business rationale", "PLM", "HIGH",
                "MEDIUM", "STANDARD_FUNCTION",
                (RequirementSourceDraft(
                    "PROJECT_EVIDENCE", project_evidence, None,
                    (project_evidence,)),),
                (RequirementAcceptanceDraft(
                    "Observable result", "Execute acceptance test", "Project data",
                    "Windows 11", "Signed acceptance report"),),
                standard, (), (), (), (), "Create review fixture",
                str(uuid.uuid4()),
            ))

        current = RequirementVersionCurrentValidator(
            survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=project_sources,
            capability_sources=capability_sources, fixed_evidence=fixed_evidence,
        )
        reviewer_service = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        owner = RequirementReviewSubjectOwner(
            repository=SqlAlchemyRequirementReviewSubjectRepository(),
            reviewers=reviewer_service, current=current, audit=audit,
            clock=lambda: now,
        )

        def start(version):
            review_id, round_id = uuid.uuid4(), uuid.uuid4()
            with runtime.unit_of_work() as tx:
                proof = owner.authorize_create(
                    tx, user_id=pm, project_id=ids["project"],
                    subject_type="REQ-03", subject_id=root.requirement_id,
                    subject_version_id=version.requirement_version_id,
                )
                assert proof is not None
                identity = ReviewIdentitySnapshot(
                    review_id, "PROJECT", ids["project"], "REQ-03",
                    root.requirement_id, "REQUIREMENT_ALL_V1", "DRAFT", None, 0,
                )
                request = ReviewSubjectStartRequest(
                    pm, identity, round_id, version.requirement_version_id,
                    (reviewer,),
                )
                prepared = owner.prepare_start_in_transaction(tx, request)
                assert prepared.basis == ()
                tx.session.execute(text("SET LOCAL session_replication_role='replica'"))
                tx.session.execute(text("""
                    INSERT INTO plm.rvw_reviews(
                      review_id,scope,project_id,subject_type,subject_id,policy_code,
                      review_state,active_round_id,lock_version,created_by)
                    VALUES (:review,'PROJECT',:project,'REQ-03',:requirement,
                      'REQUIREMENT_ALL_V1','IN_REVIEW',:round,1,:actor)
                """), {"review": review_id, "project": ids["project"],
                        "requirement": root.requirement_id,
                        "round": round_id, "actor": pm})
                tx.session.execute(text("""
                    INSERT INTO plm.rvw_review_rounds(
                      review_round_id,review_id,scope,project_id,round_no,
                      subject_version_id,round_state,lock_version,started_by,started_at)
                    VALUES (:round,:review,'PROJECT',:project,1,:version,
                      'IN_REVIEW',0,:actor,:started)
                """), {"round": round_id, "review": review_id,
                        "project": ids["project"],
                        "version": version.requirement_version_id,
                        "actor": pm, "started": now})
                tx.session.execute(text("SET LOCAL session_replication_role='origin'"))
                owner.finalize_start_in_transaction(tx, request)
                owner.assert_active_lock_in_transaction(tx, request)
                tx.commit()
            return review_id, round_id

        def terminal(version, review_id, round_id, decision_kind):
            fixed, progress = fixed_round(
                now=now, review_id=review_id, round_id=round_id,
                project_id=ids["project"], requirement_id=root.requirement_id,
                version_id=version.requirement_version_id, actor_id=pm,
                reviewer_id=reviewer, fingerprint=version.content_fingerprint,
            )
            decision = ReviewDecisionSnapshot(
                uuid.uuid4(), round_id, reviewer, decision_kind, now,
                "Needs update" if decision_kind is ReviewDecisionKind.RETURN else None,
            )
            transition = ReviewSubjectTransition(
                reviewer, uuid.uuid4(), fixed,
                progress.record_decision(decision), now,
            )
            with runtime.unit_of_work() as tx:
                owner.require_transition_access_in_transaction(tx, transition)
                state = transition.after_progress.state.value
                tx.session.execute(text("SET LOCAL session_replication_role='replica'"))
                tx.session.execute(text(
                    "UPDATE plm.rvw_reviews SET review_state=:state,"
                    "active_round_id=NULL,lock_version=2 WHERE review_id=:review"
                ), {"state": state, "review": review_id})
                tx.session.execute(text(
                    "UPDATE plm.rvw_review_rounds SET round_state=:state,"
                    "lock_version=1 WHERE review_round_id=:round"
                ), {"state": state, "round": round_id})
                tx.session.execute(text("SET LOCAL session_replication_role='origin'"))
                owner.consume_terminal_in_transaction(tx, transition)
                owner.assert_terminal_consumed_in_transaction(tx, transition)
                tx.commit()

        first = create_version(None)
        review1, round1 = start(first)
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='A08 current drift' WHERE evidence_id=%s",
                (project_evidence,),
            )
        fixed1, progress1 = fixed_round(
            now=now, review_id=review1, round_id=round1,
            project_id=ids["project"], requirement_id=root.requirement_id,
            version_id=first.requirement_version_id, actor_id=pm,
            reviewer_id=reviewer, fingerprint=first.content_fingerprint,
        )
        stale = ReviewSubjectTransition(
            reviewer, uuid.uuid4(), fixed1,
            progress1.record_decision(ReviewDecisionSnapshot(
                uuid.uuid4(), round1, reviewer,
                ReviewDecisionKind.APPROVE, now,
            )), now,
        )
        try:
            with runtime.unit_of_work() as tx:
                owner.require_transition_access_in_transaction(tx, stale)
        except ReviewSubjectAccessDenied:
            pass
        else:
            raise AssertionError("current source drift must block approval")
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                "eligibility_reason='A08 restored' WHERE evidence_id=%s",
                (project_evidence,),
            )
        terminal(first, review1, round1, ReviewDecisionKind.APPROVE)

        second = create_version(first.requirement_version_id)
        review2, round2 = start(second)
        terminal(second, review2, round2, ReviewDecisionKind.APPROVE)
        third = create_version(second.requirement_version_id)
        review3, round3 = start(third)
        terminal(third, review3, round3, ReviewDecisionKind.RETURN)

        with connect(database) as db:
            root_row = db.execute(
                "SELECT current_approved_version_ref,lock_version FROM "
                "plm.req_requirements WHERE requirement_id=%s",
                (root.requirement_id,),
            ).fetchone()
            assert root_row == (second.requirement_version_id, 9), root_row
            states = db.execute(
                "SELECT version_state FROM plm.req_requirement_versions WHERE "
                "requirement_id=%s ORDER BY version_no", (root.requirement_id,),
            ).fetchall()
            assert states == [("SUPERSEDED",), ("APPROVED",), ("RETURNED",)], states
            events = db.execute(
                "SELECT event_type,lock_version FROM "
                "plm.req_requirement_review_state_results WHERE requirement_id=%s "
                "ORDER BY lock_version", (root.requirement_id,),
            ).fetchall()
            assert events == [
                ("START", 2), ("APPROVED", 3), ("START", 5),
                ("APPROVED", 6), ("START", 8), ("RETURNED", 9),
            ], events
            audit_actions = db.execute(
                "SELECT action FROM plm.aud_events WHERE target_object_type='REQ-03' "
                "AND action IN ('REQUIREMENT_VERSION_APPROVED',"
                "'REQUIREMENT_VERSION_RETURNED','REQUIREMENT_VERSION_WITHDRAWN') "
                "ORDER BY occurred_at",
            ).fetchall()
            assert [row[0] for row in audit_actions] == [
                "REQUIREMENT_VERSION_APPROVED",
                "REQUIREMENT_VERSION_APPROVED",
                "REQUIREMENT_VERSION_RETURNED",
            ], audit_actions
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)
            ))
    print(
        "REQ_01_A08_A02_P02_REVIEW_OWNER_PASS: latest draft authorization, "
        "reviewer qualification, start/result binding, current-fact approval, "
        "supersede, return, audit and drift verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
