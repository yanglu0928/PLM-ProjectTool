"""Windows 11/PostgreSQL 18 proof for the Handover Review internal chain."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.infrastructure.task_read_repository import (
    SqlAlchemyAITaskReadRepository,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.review_start_access import (
    SqlAlchemyReviewStartAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.capability.infrastructure.read_repository import (
    SqlAlchemyCapabilityReadRepository,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.application.create_analysis import (
    CreateHandoverAnalysis, HandoverAnalysisCreateService,
)
from plm_assistant.modules.handover.application.create_version import (
    CreateHandoverVersion, HandoverAnalysisItemDraft,
    HandoverCapabilityItemRef, HandoverItemOptionDraft,
    HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.review_subject import (
    HandoverReviewSubjectOwner,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverSourceValidator,
)
from plm_assistant.modules.handover.infrastructure.analysis_create_repository import (
    SqlAlchemyHandoverAnalysisCreateRepository,
)
from plm_assistant.modules.handover.infrastructure.review_subject_repository import (
    SqlAlchemyHandoverReviewSubjectRepository,
)
from plm_assistant.modules.handover.infrastructure.version_create_repository import (
    SqlAlchemyHandoverVersionCreateRepository,
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
from plm_assistant.modules.review.application.create_review import (
    CreateReview, ReviewCreateService,
)
from plm_assistant.modules.review.application.start_round import (
    ReviewStartService, StartReviewRound,
)
from plm_assistant.modules.review.application.transition_command import (
    DecideReviewRound, ReviewTransitionCommandService, WithdrawReviewRound,
)
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.review.infrastructure.transition_repository import (
    SqlAlchemyReviewTransitionRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py",
    "hnd_review_owner_fixture",
)
connect, seed_user, CSRF = fixture.connect, fixture.seed_user, fixture.CSRF
Guard = fixture.Guard


def main() -> None:
    name = "hnd01a04p02_" + uuid.uuid4().hex[:8]
    manager_token, reviewer_token = b"m" * 32, b"r" * 32
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
                    manager = seed_user(
                        db, "Handover Review Manager", "NONE", manager_token,
                    )
                    reviewer = seed_user(
                        db, "Handover Review Customer", "NONE", reviewer_token,
                    )
                    project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDREVIEW2','hndreview2','Handover Review',%s) "
                        "RETURNING project_id", (manager,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments"
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'HND','hnd','Handover') RETURNING department_id",
                        (project,),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.prj_project_members"
                        "(project_id,user_id,department_id,project_role) VALUES "
                        "(%s,%s,%s,'PROJECT_MANAGER'),"
                        "(%s,%s,%s,'CUSTOMER_MANAGER')",
                        (project, manager, department,
                         project, reviewer, department),
                    )
                    source = fixture.seed_project_document(
                        db, manager, project, "review-source",
                    )
                    evidence, baseline, cap_version, cap_item, cap_row = (
                        uuid.uuid4() for _ in range(5)
                    )
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute(
                            "INSERT INTO plm.evd_evidence_records"
                            "(evidence_id,scope,project_id,document_id,"
                            "document_version_id,locator_type,locator_schema_version,"
                            "locator_payload,content_fingerprint,display_label,"
                            "eligibility_state,eligibility_reason,created_by) VALUES "
                            "(%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,"
                            "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,"
                            "'Review evidence','ELIGIBLE','fixture',%s)",
                            (evidence, project, source.document_id,
                             source.document_version_id, b"e" * 32, manager),
                        )
                        cap_ref = "sha256:" + "b" * 64
                        db.execute(
                            "INSERT INTO plm.cap_baselines"
                            "(baseline_id,baseline_code,name,baseline_state,"
                            "source_collection_ref,current_approved_version_ref,"
                            "created_by) VALUES "
                            "(%s,'HND.REVIEW','Review','ACTIVE',%s,%s,%s)",
                            (baseline, cap_ref, cap_version, manager),
                        )
                        db.execute(
                            "INSERT INTO plm.cap_baseline_versions"
                            "(baseline_version_id,baseline_id,version_no,"
                            "version_state,source_collection_ref,content_fingerprint,"
                            "declared_item_count,declared_document_ref_count,"
                            "declared_evidence_ref_count,created_by) VALUES "
                            "(%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)",
                            (cap_version, baseline, cap_ref, b"c" * 32, manager),
                        )
                        db.execute(
                            "INSERT INTO plm.cap_items"
                            "(capability_item_row_id,baseline_version_id,baseline_id,"
                            "capability_item_id,ordinal,capability_code,domain_name,"
                            "module_name,feature_name,name,description,boundary_text,"
                            "item_state) VALUES "
                            "(%s,%s,%s,%s,0,'HND.REVIEW.ITEM','PLM','Handover',"
                            "'Review','Review','Review capability','Project','AVAILABLE')",
                            (cap_row, cap_version, baseline, cap_item),
                        )
                now = datetime.now(timezone.utc)
                guard, receipts = Guard(), SqlAlchemyIdempotencyReceipts()
                audit = AuditService(SqlAlchemyAuditRepository())
                access = SqlAlchemyReviewStartAccess()
                project_repository = SqlAlchemyProjectAuthorizationRepository()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=project_repository,
                )
                sources = HandoverSourceValidator(
                    SqlAlchemyDocumentReadRepository()
                )
                evidence_port = SqlAlchemyEvidenceFixedSourceRepository()
                capability_port = SqlAlchemyCapabilityReadRepository()
                ai_port = SqlAlchemyAITaskReadRepository()
                analysis = HandoverAnalysisCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, authorization=authorization,
                    sources=sources,
                    repository=SqlAlchemyHandoverAnalysisCreateRepository(),
                    receipts=receipts, audit=audit, clock=lambda: now,
                ).create(CreateHandoverAnalysis(
                    manager_token, CSRF, uuid.uuid4(), project,
                    "Review handover", (source,), str(uuid.uuid4()),
                ))
                version_service = HandoverVersionCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, authorization=authorization,
                    sources=sources, evidence=evidence_port,
                    capabilities=capability_port, ai_tasks=ai_port,
                    repository=SqlAlchemyHandoverVersionCreateRepository(),
                    receipts=receipts, audit=audit, clock=lambda: now,
                )
                with runtime.unit_of_work() as tx:
                    assert sources.validate(
                        tx, project_id=project, references=(source,),
                    ).source_set_ref == analysis.source_set_ref
                    cap_probe = capability_port.get_version(
                        tx, visibility="CURRENT_APPROVED",
                        baseline_id=baseline,
                        baseline_version_id=cap_version,
                    )
                    item_probe = capability_port.list_items(
                        tx, visibility="CURRENT_APPROVED",
                        baseline_id=baseline,
                        baseline_version_id=cap_version,
                        after_ordinal=None, limit=501,
                    )
                    evidence_probe = evidence_port.get_for_trace(
                        tx, scope="PROJECT", project_id=project,
                        evidence_id=evidence,
                    )
                    assert cap_probe is not None and cap_probe.state == "APPROVED"
                    assert len(item_probe) == 1 and evidence_probe is not None

                def item(item_id: uuid.UUID) -> HandoverAnalysisItemDraft:
                    return HandoverAnalysisItemDraft(
                        item_id, "NEED_CONFIRM", "Confirm scope",
                        "Customer scope is unresolved", "Delivery affected",
                        "HIGH", "HIGH", "Confirm one option", "Which scope?",
                        {"fields": [{"name": "scope", "format": "text",
                                     "example": "Option A", "required": True}]},
                        False, (evidence,),
                        (HandoverCapabilityItemRef(cap_item),),
                        (HandoverItemOptionDraft("A", "Option A"),
                         HandoverItemOptionDraft("B", "Option B")),
                    )

                first_item = uuid.uuid4()
                first_command = CreateHandoverVersion(
                    manager_token, CSRF, uuid.uuid4(), project,
                    analysis.handover_analysis_id, 0, (source,), baseline,
                    cap_version, (item(first_item),), (), str(uuid.uuid4()),
                )
                first = version_service.create(first_command)

                def add_action(version_id: uuid.UUID, item_id: uuid.UUID) -> None:
                    with connect(name) as db, db.transaction():
                        action_id, at = uuid.uuid4(), datetime.now(timezone.utc)
                        db.execute(
                            "INSERT INTO plm.hnd_action_items"
                            "(action_item_id,project_id,source_kind,"
                            "source_analysis_version_ref,source_item_id,action_type,"
                            "title,requested_input_spec,owner_ref,due_at,priority,"
                            "action_state,created_by,created_reason,created_at,"
                            "updated_at,lock_version) VALUES "
                            "(%s,%s,'ANALYSIS_ITEM',%s,%s,'CONFIRM_DECISION',"
                            "'Confirm scope','{\"fields\":[]}'::jsonb,%s,"
                            "%s + interval '7 days','HIGH','OPEN',%s,"
                            "'Review coverage',%s,%s,0)",
                            (action_id, project, version_id, item_id, reviewer,
                             at, manager, at, at),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_state_events"
                            "(action_state_event_id,action_item_id,project_id,"
                            "sequence_no,from_state,to_state,actor_id,reason,"
                            "occurred_at,trace_id) VALUES "
                            "(%s,%s,%s,0,NULL,'OPEN',%s,'Review coverage',%s,%s)",
                            (uuid.uuid4(), action_id, project, manager, at,
                             uuid.uuid4()),
                        )

                add_action(first.handover_analysis_version_id, first_item)
                reviewer_service = ProjectReviewerQualificationService(
                    users=SqlAlchemyReviewUserAccess(),
                    projects=project_repository,
                )
                owner = HandoverReviewSubjectOwner(
                    repository=SqlAlchemyHandoverReviewSubjectRepository(),
                    reviewers=reviewer_service, sources=sources,
                    evidence=evidence_port, capabilities=capability_port,
                    ai_tasks=ai_port, audit=audit, clock=lambda: now,
                )
                create_service = ReviewCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    projects=authorization, license_guard=guard,
                    repository=SqlAlchemyReviewCreationRepository(),
                    receipts=receipts, audit=audit, subjects=owner,
                    clock=lambda: now,
                )
                start_service = ReviewStartService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    projects=authorization, reviewers=reviewer_service,
                    license_guard=guard,
                    repository=SqlAlchemyReviewStartRepository(),
                    receipts=receipts, audit=audit, subjects=owner,
                    clock=lambda: now,
                )
                transition_service = ReviewTransitionCommandService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    projects=authorization, license_guard=guard,
                    repository=SqlAlchemyReviewTransitionRepository(),
                    receipts=receipts, audit=audit, subjects=owner,
                    clock=lambda: now,
                )

                def create_start(version_id: uuid.UUID):
                    created = create_service.create_idempotent(CreateReview(
                        manager_token, CSRF, uuid.uuid4(), project, "HND-02",
                        analysis.handover_analysis_id, version_id,
                    ), idempotency_key=str(uuid.uuid4()))
                    started = start_service.start_idempotent(StartReviewRound(
                        manager_token, CSRF, project, created.review_id,
                        version_id, (reviewer,), "HANDOVER_ALL_V1", 0,
                        uuid.uuid4(),
                    ), idempotency_key=str(uuid.uuid4()))
                    return created, started

                review_one, round_one = create_start(
                    first.handover_analysis_version_id
                )
                approved = transition_service.decide_idempotent(
                    DecideReviewRound(
                        reviewer_token, CSRF, project, review_one.review_id,
                        round_one.round_id, uuid.uuid4(),
                        ReviewDecisionKind.APPROVE, "Approved for handover",
                    ), idempotency_key=str(uuid.uuid4()),
                )
                assert approved.state.value == "APPROVED"

                with connect(name) as db:
                    root_lock = db.execute(
                        "SELECT lock_version FROM plm.hnd_analyses "
                        "WHERE handover_analysis_id=%s",
                        (analysis.handover_analysis_id,),
                    ).fetchone()[0]
                second_item = uuid.uuid4()
                second = version_service.create(CreateHandoverVersion(
                    manager_token, CSRF, uuid.uuid4(), project,
                    analysis.handover_analysis_id, root_lock, (source,),
                    baseline, cap_version, (item(second_item),), (),
                    str(uuid.uuid4()),
                ))
                add_action(second.handover_analysis_version_id, second_item)
                review_two, round_two = create_start(
                    second.handover_analysis_version_id
                )
                withdrawn = transition_service.withdraw_idempotent(
                    WithdrawReviewRound(
                        manager_token, CSRF, project, review_two.review_id,
                        round_two.round_id, uuid.uuid4(), 1,
                        "Source scope changed",
                    ), idempotency_key=str(uuid.uuid4()),
                )
                assert withdrawn.state.value == "WITHDRAWN"
                with connect(name) as db:
                    row = db.execute(
                        "SELECT a.current_approved_version_ref,"
                        "array_agg(v.version_state ORDER BY v.version_no) "
                        "FROM plm.hnd_analyses a JOIN plm.hnd_analysis_versions v "
                        "ON v.handover_analysis_id=a.handover_analysis_id "
                        "WHERE a.handover_analysis_id=%s "
                        "GROUP BY a.current_approved_version_ref",
                        (analysis.handover_analysis_id,),
                    ).fetchone()
                    assert row == (
                        first.handover_analysis_version_id,
                        ["APPROVED", "RETURNED"],
                    ), row
                    states = db.execute(
                        "SELECT v.version_no,array_agg(i.item_state ORDER BY i.ordinal) "
                        "FROM plm.hnd_analysis_versions v "
                        "JOIN plm.hnd_analysis_items i ON "
                        "i.handover_analysis_version_id="
                        "v.handover_analysis_version_id "
                        "WHERE v.handover_analysis_id=%s GROUP BY v.version_no "
                        "ORDER BY v.version_no",
                        (analysis.handover_analysis_id,),
                    ).fetchall()
                    assert states == [(1, ["CONFIRMED"]),
                                      (2, ["CANDIDATE"])], states
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE action IN "
                        "('HND_VERSION_APPROVED','HND_VERSION_WITHDRAWN')"
                    ).fetchone()[0] == 2
                print(
                    "HND_01_A04_A02_P02_REVIEW_OWNER_PASS: real PROJECT "
                    "Review create/start/approve/withdraw, current source and "
                    "reviewer revalidation, atomic approved pointer/item "
                    "projection and withdrawal history verified on PostgreSQL 18"
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
