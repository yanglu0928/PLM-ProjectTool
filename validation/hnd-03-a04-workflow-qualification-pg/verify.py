"""Windows 11/PostgreSQL 18 proof for Handover Workflow qualification."""

from __future__ import annotations

import hashlib
import importlib.util
import tempfile
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
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.deployment_read_access import (
    SqlAlchemyDeploymentReadAccess,
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
from plm_assistant.modules.document.application.prepare_download import (
    PrepareDownloadService,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    DocumentFixedSourceProofService,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadService,
)
from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
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
    HandoverDocumentRef, HandoverSourceValidator,
)
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowQualificationOwner,
    HandoverWorkflowQualificationOwnerError,
    HandoverWorkflowQualificationQuery,
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
from plm_assistant.modules.handover.infrastructure.workflow_qualification_repository import (
    SqlAlchemyHandoverWorkflowQualificationRepository,
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
    DecideReviewRound, ReviewTransitionCommandService,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
)
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.read_repository import (
    SqlAlchemyReviewSnapshotReadRepository,
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
    "hnd_03_a04_fixture",
)
connect, seed_user, CSRF = fixture.connect, fixture.seed_user, fixture.CSRF
Guard = fixture.Guard


_BUSINESS_TABLES = (
    ("hnd_analyses", "handover_analysis_id"),
    ("hnd_analysis_versions", "handover_analysis_version_id"),
    ("hnd_analysis_source_document_refs", "source_document_ref_id"),
    ("hnd_analysis_items", "analysis_item_row_id"),
    ("hnd_item_evidence_refs", "item_evidence_ref_id"),
    ("hnd_item_capability_refs", "item_capability_ref_id"),
    ("hnd_item_options", "item_option_id"),
    ("hnd_analysis_ai_task_refs", "ai_task_ref_id"),
    ("hnd_action_items", "action_item_id"),
    ("hnd_action_response_refs", "action_response_ref_id"),
    ("hnd_action_evidence_refs", "action_evidence_ref_id"),
    ("hnd_action_state_events", "action_state_event_id"),
    ("doc_file_objects", "file_object_id"),
    ("doc_documents", "document_id"),
    ("doc_document_versions", "document_version_id"),
    ("evd_evidence_records", "evidence_id"),
    ("cap_baselines", "baseline_id"),
    ("cap_baseline_versions", "baseline_version_id"),
    ("cap_items", "capability_item_row_id"),
    ("ai_tasks", "ai_task_id"),
    ("ai_task_input_refs", "input_ref_id"),
    ("rvw_reviews", "review_id"),
    ("rvw_review_rounds", "review_round_id"),
    ("rvw_review_assignments", "assignment_id"),
    ("rvw_review_decisions", "decision_id"),
    ("rvw_subject_snapshots", "snapshot_id"),
    ("rvw_subject_snapshot_refs", "snapshot_ref_id"),
    ("rvw_subject_locks", "subject_lock_id"),
    ("rvw_round_events", "round_event_id"),
)


def business_snapshot(database: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    values = []
    with connect(database) as db:
        for table, identity in _BUSINESS_TABLES:
            rows = db.execute(sql.SQL(
                "SELECT to_jsonb(t)::text FROM plm.{} t ORDER BY {}"
            ).format(sql.Identifier(table), sql.Identifier(identity))).fetchall()
            values.append((table, tuple(row[0] for row in rows)))
    return tuple(values)


class NoParse:
    def get_for_trace(self, *args, **kwargs):
        raise AssertionError("whole-document proof must not read parse metadata")

    def read(self, *args, **kwargs):
        raise AssertionError("whole-document proof must not read parse bytes")


class NoWriteAudit:
    def append(self, *args, **kwargs):
        raise AssertionError("qualification must not emit download audit")


class NoTrace:
    def prove(self, *args, **kwargs):
        raise AssertionError("VERIFIED action must not require resolution Trace")


def expect_closed(owner, tx, query) -> None:
    try:
        owner.qualify_in_transaction(tx, query)
    except HandoverWorkflowQualificationOwnerError as error:
        assert str(error) == "HANDOVER_WORKFLOW_NOT_QUALIFIED"
    else:
        raise AssertionError("drifted Handover facts were accepted")


def seed_document(db, *, storage: LocalFileStorage, root: Path,
                  actor: uuid.UUID, project: uuid.UUID,
                  label: str, content: bytes) -> HandoverDocumentRef:
    file_id, document_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    digest = hashlib.sha256(content).digest()
    _, locator = storage.locators(
        scope="PROJECT", project_id=project, file_object_id=file_id,
    )
    target = root / locator
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.doc_file_objects"
            "(file_object_id,scope,project_id,storage_class,storage_locator,"
            "original_name_metadata,sha256,size_bytes,detected_mime,file_state,"
            "created_by,available_at) VALUES "
            "(%s,'PROJECT',%s,'PERSISTENT',%s,%s,%s,%s,"
            "'application/pdf','AVAILABLE',%s,statement_timestamp())",
            (file_id, project, locator, f"{label}.pdf", digest,
             len(content), actor),
        )
        db.execute(
            "INSERT INTO plm.doc_documents"
            "(document_id,scope,project_id,document_category,title,"
            "original_display_name,document_state,created_by) VALUES "
            "(%s,'PROJECT',%s,'PROJECT_RECORD',%s,%s,'ACTIVE',%s)",
            (document_id, project, label, f"{label}.pdf", actor),
        )
        db.execute(
            "INSERT INTO plm.doc_document_versions"
            "(document_version_id,document_id,scope,project_id,version_no,"
            "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,"
            "created_by,availability_state,integrity_checked_at) VALUES "
            "(%s,%s,'PROJECT',%s,1,%s,%s,%s,'application/pdf','{}'::jsonb,"
            "%s,'AVAILABLE',statement_timestamp())",
            (version_id, document_id, project, file_id, digest,
             len(content), actor),
        )
    return HandoverDocumentRef(document_id, version_id)


def main() -> None:
    name = "hnd03a04_" + uuid.uuid4().hex[:10]
    manager_token, reviewer_token = b"m" * 32, b"r" * 32
    with tempfile.TemporaryDirectory(prefix="plm-hnd03-a04-") as temp:
        data_root = Path(temp).resolve()
        storage = LocalFileStorage(data_root)
        with connect("postgres") as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(name),
            ))
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
                            db, "Workflow Qualification PM", "NONE",
                            manager_token,
                        )
                        reviewer = seed_user(
                            db, "Workflow Qualification Customer", "NONE",
                            reviewer_token,
                        )
                        project = db.execute(
                            "INSERT INTO plm.prj_projects"
                            "(project_code,project_code_normalized,name,created_by) "
                            "VALUES ('HND03A04','hnd03a04','Qualification',%s) "
                            "RETURNING project_id", (manager,),
                        ).fetchone()[0]
                        department = db.execute(
                            "INSERT INTO plm.prj_departments"
                            "(project_id,department_code,department_code_normalized,"
                            "name) VALUES (%s,'HND','hnd','Handover') "
                            "RETURNING department_id", (project,),
                        ).fetchone()[0]
                        for user, role in (
                            (manager, "PROJECT_MANAGER"),
                            (reviewer, "CUSTOMER_MANAGER"),
                        ):
                            db.execute(
                                "INSERT INTO plm.prj_project_members"
                                "(project_id,user_id,department_id,project_role) "
                                "VALUES (%s,%s,%s,%s)",
                                (project, user, department, role),
                            )
                        source = seed_document(
                            db, storage=storage, root=data_root,
                            actor=manager, project=project, label="source",
                            content=b"%PDF-1.7\nqualification source\n",
                        )
                        response = seed_document(
                            db, storage=storage, root=data_root,
                            actor=manager, project=project, label="response",
                            content=b"%PDF-1.7\nverified response\n",
                        )
                        source_evidence = uuid.uuid4()
                        submit_evidence = uuid.uuid4()
                        verify_evidence = uuid.uuid4()
                        baseline, cap_version, cap_item, cap_row = (
                            uuid.uuid4() for _ in range(4)
                        )
                        ai_task = uuid.uuid4()
                        source_digest = hashlib.sha256(
                            b"%PDF-1.7\nqualification source\n"
                        ).digest()
                        response_digest = hashlib.sha256(
                            b"%PDF-1.7\nverified response\n"
                        ).digest()
                        with db.transaction():
                            db.execute("SET LOCAL session_replication_role='replica'")
                            for evidence_id, document, digest, label in (
                                (source_evidence, source, source_digest, "Source"),
                                (submit_evidence, response, response_digest,
                                 "Submission"),
                                (verify_evidence, response, response_digest,
                                 "Verification"),
                            ):
                                db.execute(
                                    "INSERT INTO plm.evd_evidence_records"
                                    "(evidence_id,scope,project_id,document_id,"
                                    "document_version_id,locator_type,"
                                    "locator_schema_version,locator_payload,"
                                    "content_fingerprint,display_label,"
                                    "eligibility_state,eligibility_reason,created_by) "
                                    "VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,"
                                    "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,"
                                    "%s,%s,'ELIGIBLE','fixture',%s)",
                                    (evidence_id, project, document.document_id,
                                     document.document_version_id, digest, label,
                                     manager),
                                )
                            cap_ref = "sha256:" + "b" * 64
                            db.execute(
                                "INSERT INTO plm.cap_baselines"
                                "(baseline_id,baseline_code,name,baseline_state,"
                                "source_collection_ref,current_approved_version_ref,"
                                "created_by) VALUES "
                                "(%s,'HND.QUALIFY','Qualify','ACTIVE',%s,%s,%s)",
                                (baseline, cap_ref, cap_version, manager),
                            )
                            db.execute(
                                "INSERT INTO plm.cap_baseline_versions"
                                "(baseline_version_id,baseline_id,version_no,"
                                "version_state,source_collection_ref,"
                                "content_fingerprint,declared_item_count,"
                                "declared_document_ref_count,"
                                "declared_evidence_ref_count,created_by) VALUES "
                                "(%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)",
                                (cap_version, baseline, cap_ref, b"c" * 32,
                                 manager),
                            )
                            db.execute(
                                "INSERT INTO plm.cap_items"
                                "(capability_item_row_id,baseline_version_id,"
                                "baseline_id,capability_item_id,ordinal,"
                                "capability_code,domain_name,module_name,feature_name,"
                                "name,description,boundary_text,item_state) VALUES "
                                "(%s,%s,%s,%s,0,'HND.QUALIFY.ITEM','PLM',"
                                "'Handover','Qualify','Qualify','Qualification',"
                                "'Project','AVAILABLE')",
                                (cap_row, cap_version, baseline, cap_item),
                            )
                            db.execute(
                                "INSERT INTO plm.ai_tasks"
                                "(ai_task_id,scope,project_id,task_type,requested_by,"
                                "input_fingerprint,prompt_policy_ref,output_schema_ref,"
                                "context_policy_ref,task_state,suggestion_state,"
                                "trace_id,started_at,completed_at) VALUES "
                                "(%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'gap.v1',"
                                "'gap.output.v1','project.v1','SUCCEEDED','AVAILABLE',"
                                "%s,statement_timestamp(),statement_timestamp())",
                                (ai_task, project, manager, b"a" * 32,
                                 uuid.uuid4()),
                            )
                            db.execute(
                                "INSERT INTO plm.ai_task_input_refs"
                                "(input_ref_id,ai_task_id,ref_ordinal,scope,"
                                "project_id,owner_module,object_type,object_id,"
                                "version_id) VALUES "
                                "(%s,%s,1,'PROJECT',%s,'document',"
                                "'DOCUMENT_VERSION',%s,%s)",
                                (uuid.uuid4(), ai_task, project,
                                 source.document_id,
                                 source.document_version_id),
                            )

                    now = datetime.now(timezone.utc)
                    guard = Guard()
                    access = SqlAlchemyReviewStartAccess()
                    receipts = SqlAlchemyIdempotencyReceipts()
                    audit = AuditService(SqlAlchemyAuditRepository())
                    project_repository = SqlAlchemyProjectAuthorizationRepository()
                    authorization = ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=project_repository,
                    )
                    source_validator = HandoverSourceValidator(
                        SqlAlchemyDocumentReadRepository()
                    )
                    evidence_repository = SqlAlchemyEvidenceFixedSourceRepository()
                    capability_repository = SqlAlchemyCapabilityReadRepository()
                    ai_repository = SqlAlchemyAITaskReadRepository()
                    with runtime.unit_of_work() as tx:
                        assert source_validator.validate(
                            tx, project_id=project, references=(source,),
                        ).documents == (source,)
                        assert capability_repository.get_version(
                            tx, visibility="CURRENT_APPROVED",
                            baseline_id=baseline,
                            baseline_version_id=cap_version,
                        ) is not None
                        assert len(capability_repository.list_items(
                            tx, visibility="CURRENT_APPROVED",
                            baseline_id=baseline,
                            baseline_version_id=cap_version,
                            after_ordinal=None, limit=501,
                        )) == 1
                        assert evidence_repository.get_for_trace(
                            tx, scope="PROJECT", project_id=project,
                            evidence_id=source_evidence,
                        ) is not None
                        task_probe = ai_repository.get(
                            tx, ai_task_id=ai_task, project_id=project,
                        )
                        assert task_probe is not None
                        assert task_probe.task_type == "GAP_ANALYSIS"
                        assert task_probe.task_state == "SUCCEEDED"
                    analysis = HandoverAnalysisCreateService(
                        unit_of_work=runtime.unit_of_work, access=access,
                        license_guard=guard, authorization=authorization,
                        sources=source_validator,
                        repository=SqlAlchemyHandoverAnalysisCreateRepository(),
                        receipts=receipts, audit=audit, clock=lambda: now,
                    ).create(CreateHandoverAnalysis(
                        manager_token, CSRF, uuid.uuid4(), project,
                        "Workflow qualification", (source,), str(uuid.uuid4()),
                    ))
                    item_id = uuid.uuid4()
                    item = HandoverAnalysisItemDraft(
                        item_id, "NEED_CONFIRM", "Confirm scope",
                        "Scope remains unresolved", "Delivery affected",
                        "HIGH", "HIGH", "Confirm option A", "Which scope?",
                        {"fields": [{"name": "scope", "format": "text",
                                     "example": "A", "required": True}]},
                        False, (source_evidence,),
                        (HandoverCapabilityItemRef(cap_item),),
                        (HandoverItemOptionDraft("A", "Option A"),
                         HandoverItemOptionDraft("B", "Option B")),
                    )
                    version = HandoverVersionCreateService(
                        unit_of_work=runtime.unit_of_work, access=access,
                        license_guard=guard, authorization=authorization,
                        sources=source_validator, evidence=evidence_repository,
                        capabilities=capability_repository, ai_tasks=ai_repository,
                        repository=SqlAlchemyHandoverVersionCreateRepository(),
                        receipts=receipts, audit=audit, clock=lambda: now,
                    ).create(CreateHandoverVersion(
                        manager_token, CSRF, uuid.uuid4(), project,
                        analysis.handover_analysis_id, 0, (source,), baseline,
                        cap_version, (item,), (ai_task,), str(uuid.uuid4()),
                    ))
                    action_id = uuid.uuid4()
                    with connect(name) as db, db.transaction():
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
                            "'Qualification coverage',%s,%s,0)",
                            (action_id, project,
                             version.handover_analysis_version_id, item_id,
                             reviewer, now, manager, now, now),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_state_events"
                            "(action_state_event_id,action_item_id,project_id,"
                            "sequence_no,from_state,to_state,actor_id,reason,"
                            "occurred_at,trace_id) VALUES "
                            "(%s,%s,%s,0,NULL,'OPEN',%s,"
                            "'Qualification coverage',%s,%s)",
                            (uuid.uuid4(), action_id, project, manager, now,
                             uuid.uuid4()),
                        )

                    reviewers = ProjectReviewerQualificationService(
                        users=SqlAlchemyReviewUserAccess(),
                        projects=project_repository,
                    )
                    subject = HandoverReviewSubjectOwner(
                        repository=SqlAlchemyHandoverReviewSubjectRepository(),
                        reviewers=reviewers, sources=source_validator,
                        evidence=evidence_repository,
                        capabilities=capability_repository,
                        ai_tasks=ai_repository, audit=audit,
                        clock=lambda: now,
                    )
                    created = ReviewCreateService(
                        unit_of_work=runtime.unit_of_work, access=access,
                        projects=authorization, license_guard=guard,
                        repository=SqlAlchemyReviewCreationRepository(),
                        receipts=receipts, audit=audit, subjects=subject,
                        clock=lambda: now,
                    ).create_idempotent(CreateReview(
                        manager_token, CSRF, uuid.uuid4(), project, "HND-02",
                        analysis.handover_analysis_id,
                        version.handover_analysis_version_id,
                    ), idempotency_key=str(uuid.uuid4()))
                    started = ReviewStartService(
                        unit_of_work=runtime.unit_of_work, access=access,
                        projects=authorization, reviewers=reviewers,
                        license_guard=guard,
                        repository=SqlAlchemyReviewStartRepository(),
                        receipts=receipts, audit=audit, subjects=subject,
                        clock=lambda: now,
                    ).start_idempotent(StartReviewRound(
                        manager_token, CSRF, project, created.review_id,
                        version.handover_analysis_version_id, (reviewer,),
                        "HANDOVER_ALL_V1", 0, uuid.uuid4(),
                    ), idempotency_key=str(uuid.uuid4()))
                    approved = ReviewTransitionCommandService(
                        unit_of_work=runtime.unit_of_work, access=access,
                        projects=authorization, license_guard=guard,
                        repository=SqlAlchemyReviewTransitionRepository(),
                        receipts=receipts, audit=audit, subjects=subject,
                        clock=lambda: now,
                    ).decide_idempotent(DecideReviewRound(
                        reviewer_token, CSRF, project, created.review_id,
                        started.round_id, uuid.uuid4(),
                        ReviewDecisionKind.APPROVE,
                        "Approved for qualification",
                    ), idempotency_key=str(uuid.uuid4()))
                    assert approved.state.value == "APPROVED"

                    with connect(name) as db, db.transaction():
                        db.execute(
                            "INSERT INTO plm.hnd_action_state_events"
                            "(action_state_event_id,action_item_id,project_id,"
                            "sequence_no,from_state,to_state,actor_id,reason,"
                            "occurred_at,trace_id) VALUES "
                            "(%s,%s,%s,1,'OPEN','IN_PROGRESS',%s,"
                            "'Work started',%s,%s)",
                            (uuid.uuid4(), action_id, project, reviewer, now,
                             uuid.uuid4()),
                        )
                        db.execute(
                            "UPDATE plm.hnd_action_items SET "
                            "action_state='IN_PROGRESS',updated_by=%s,updated_at=%s,"
                            "lock_version=1 WHERE action_item_id=%s",
                            (reviewer, now, action_id),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_response_refs"
                            "(action_response_ref_id,action_item_id,project_id,"
                            "document_id,document_version_id,ordinal) VALUES "
                            "(%s,%s,%s,%s,%s,0)",
                            (uuid.uuid4(), action_id, project,
                             response.document_id,
                             response.document_version_id),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_evidence_refs"
                            "(action_evidence_ref_id,action_item_id,project_id,"
                            "evidence_id,purpose,ordinal) VALUES "
                            "(%s,%s,%s,%s,'SUBMISSION',0)",
                            (uuid.uuid4(), action_id, project, submit_evidence),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_state_events"
                            "(action_state_event_id,action_item_id,project_id,"
                            "sequence_no,from_state,to_state,actor_id,reason,"
                            "occurred_at,trace_id) VALUES "
                            "(%s,%s,%s,2,'IN_PROGRESS','SUBMITTED',%s,"
                            "'Response submitted',%s,%s)",
                            (uuid.uuid4(), action_id, project, reviewer, now,
                             uuid.uuid4()),
                        )
                        db.execute(
                            "UPDATE plm.hnd_action_items SET "
                            "action_state='SUBMITTED',submitted_at=%s,updated_by=%s,"
                            "updated_at=%s,lock_version=2 WHERE action_item_id=%s",
                            (now, reviewer, now, action_id),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_evidence_refs"
                            "(action_evidence_ref_id,action_item_id,project_id,"
                            "evidence_id,purpose,ordinal) VALUES "
                            "(%s,%s,%s,%s,'VERIFICATION',1)",
                            (uuid.uuid4(), action_id, project, verify_evidence),
                        )
                        db.execute(
                            "INSERT INTO plm.hnd_action_state_events"
                            "(action_state_event_id,action_item_id,project_id,"
                            "sequence_no,from_state,to_state,actor_id,reason,"
                            "occurred_at,trace_id) VALUES "
                            "(%s,%s,%s,3,'SUBMITTED','VERIFIED',%s,"
                            "'Response verified',%s,%s)",
                            (uuid.uuid4(), action_id, project, manager, now,
                             uuid.uuid4()),
                        )
                        db.execute(
                            "UPDATE plm.hnd_action_items SET "
                            "action_state='VERIFIED',verified_by=%s,verified_at=%s,updated_by=%s,"
                            "updated_at=%s,lock_version=3 WHERE action_item_id=%s",
                            (manager, now, manager, now, action_id),
                        )

                    reads = DocumentReadService(
                        unit_of_work=runtime.unit_of_work,
                        session_access=SqlAlchemyProjectReadAccess(),
                        admin_access=SqlAlchemyDeploymentReadAccess(),
                        project_facts=project_repository,
                        license_guard=guard,
                        repository=SqlAlchemyDocumentReadRepository(),
                        clock=lambda: now,
                    )
                    downloads = PrepareDownloadService(
                        reader=reads, storage=storage,
                        unit_of_work=runtime.unit_of_work,
                        audit=NoWriteAudit(),
                    )
                    document_proofs = DocumentFixedSourceProofService(
                        documents=reads, downloads=downloads,
                        parse_metadata=NoParse(), parse_results=NoParse(),
                    )
                    evidence_proofs = EvidenceFixedProjectSourceService(
                        sessions=SqlAlchemyProjectReadAccess(),
                        projects=project_repository,
                        evidence=evidence_repository,
                        documents=document_proofs, clock=lambda: now,
                    )
                    owner = HandoverWorkflowQualificationOwner(
                        repository=(
                            SqlAlchemyHandoverWorkflowQualificationRepository()
                        ),
                        sources=source_validator, documents=document_proofs,
                        evidence=evidence_proofs,
                        capabilities=capability_repository,
                        ai_tasks=ai_repository,
                        reviews=SqlAlchemyReviewSnapshotReadRepository(),
                        trace_proofs=NoTrace(), clock=lambda: now,
                    )
                    query = HandoverWorkflowQualificationQuery(
                        manager_token, uuid.uuid4(), project,
                        analysis.handover_analysis_id, "HANDOVER_ISSUES",
                    )
                    before_qualification = business_snapshot(name)
                    with runtime.unit_of_work() as tx:
                        result = owner.qualify_in_transaction(tx, query)
                        assert result.item_key == "HANDOVER_ISSUES"
                        assert {value.evidence_id for value in result.evidence} == {
                            source_evidence, submit_evidence, verify_evidence,
                        }
                        assert result.review.review_id == created.review_id
                        with connect(name) as rival:
                            for table, identity, value in (
                                ("hnd_analyses", "handover_analysis_id",
                                 analysis.handover_analysis_id),
                                ("hnd_analysis_versions",
                                 "handover_analysis_version_id",
                                 version.handover_analysis_version_id),
                                ("hnd_analysis_items", "analysis_item_id",
                                 item_id),
                                ("hnd_action_items", "action_item_id",
                                 action_id),
                                ("evd_evidence_records", "evidence_id",
                                 source_evidence),
                                ("doc_document_versions",
                                 "document_version_id",
                                 source.document_version_id),
                                ("rvw_reviews", "review_id",
                                 created.review_id),
                                ("rvw_review_rounds", "review_round_id",
                                 started.round_id),
                            ):
                                try:
                                    rival.execute(sql.SQL(
                                        "SELECT 1 FROM plm.{} WHERE {}=%s "
                                        "FOR UPDATE NOWAIT"
                                    ).format(sql.Identifier(table),
                                             sql.Identifier(identity)), (value,))
                                except Exception as error:
                                    assert getattr(error, "sqlstate", None) == "55P03", (
                                        table, getattr(error, "sqlstate", None),
                                    )
                                    rival.rollback()
                                else:
                                    raise AssertionError(
                                        f"qualification did not lock {table}"
                                    )
                    assert business_snapshot(name) == before_qualification

                    with connect(name) as db:
                        db.execute(
                            "UPDATE plm.evd_evidence_records SET "
                            "eligibility_state='INELIGIBLE',"
                            "eligibility_reason='drift proof',updated_by=%s,"
                            "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                            "WHERE evidence_id=%s", (manager, source_evidence,),
                        )
                    with runtime.unit_of_work() as tx:
                        expect_closed(owner, tx, query)
                    with connect(name) as db:
                        db.execute(
                            "UPDATE plm.evd_evidence_records SET "
                            "eligibility_state='ELIGIBLE',"
                            "eligibility_reason='restored',updated_by=%s,"
                            "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                            "WHERE evidence_id=%s", (manager, source_evidence,),
                        )
                    with connect(name) as db:
                        response_file_id = db.execute(
                            "SELECT file_object_id FROM plm.doc_document_versions "
                            "WHERE document_version_id=%s",
                            (response.document_version_id,),
                        ).fetchone()[0]
                    response_file = data_root / storage.locators(
                        scope="PROJECT", project_id=project,
                        file_object_id=response_file_id,
                    )[1]
                    original = response_file.read_bytes()
                    response_file.write_bytes(original[:-1] + b"!")
                    with runtime.unit_of_work() as tx:
                        expect_closed(owner, tx, query)
                    response_file.write_bytes(original)
                    print(
                        "HND_03_A04_WORKFLOW_QUALIFICATION_PG_PASS: real approved "
                        "Handover/Review, fixed Document bytes, Evidence/Capability/"
                        "AI current facts, VERIFIED Action, PostgreSQL share locks, "
                        "zero business writes and Evidence/file drift rejection verified"
                    )
                finally:
                    runtime.dispose()
            finally:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(
                    sql.Identifier(name),
                ))


if __name__ == "__main__":
    main()
