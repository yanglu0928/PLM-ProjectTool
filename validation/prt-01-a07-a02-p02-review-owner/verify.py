"""Windows 11/PostgreSQL 18 proof for the Prototype Review Subject Owner."""

from __future__ import annotations

import hashlib
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
from plm_assistant.modules.auth.infrastructure.review_start_access import (
    SqlAlchemyReviewStartAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import (
    SqlAlchemyPrototypeDocumentArtifactProof,
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
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.prototype.application.create_version import (
    VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.current_version import (
    PrototypeVersionCurrentValidator,
)
from plm_assistant.modules.prototype.application.approval_trace import (
    PrototypeApprovalTraceOwner,
)
from plm_assistant.modules.prototype.application.review_subject import (
    PrototypeReviewSubjectOwner,
)
from plm_assistant.modules.prototype.application.submit_review import (
    PrototypeReviewSubmissionError,
    PrototypeReviewSubmissionService,
    SubmitPrototypeVersionReview,
)
from plm_assistant.modules.prototype.infrastructure.review_subject_repository import (
    SqlAlchemyPrototypeReviewSubjectRepository,
)
from plm_assistant.modules.prototype.infrastructure.approval_trace_repository import (
    SqlAlchemyPrototypeApprovalTraceRepository,
)
from plm_assistant.modules.prototype.infrastructure.version_create_repository import (
    SqlAlchemyPrototypeVersionCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.version_input_proofs import (
    SqlAlchemyPrototypeVersionTemplateProof,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.review.application.create_review import (
    CreateReview,
    ReviewCreateService,
)
from plm_assistant.modules.review.application.start_round import (
    ReviewStartService,
    StartReviewRound,
)
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.application.transition_command import (
    DecideReviewRound,
    ReviewTransitionCommandError,
    ReviewTransitionCommandService,
    WithdrawReviewRound,
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
from plm_assistant.modules.trace.infrastructure.create_repository import (
    SqlAlchemyTraceCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
fixture = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, seed_user = fixture["connect"], fixture["seed_user"]
Guard = fixture["Guard"]
CSRF = b"c" * 32


def main(*, verify_submission: bool = False) -> None:
    database = "prt01a07p02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        manager_token, reviewer_token = b"m" * 32, b"r" * 32
        ids = {name: uuid.uuid4() for name in (
            "prototype", "template", "template_version", "requirement",
            "requirement_version", "requirement_review", "requirement_round",
            "file", "document", "document_version",
        )}
        with connect(database) as db:
            manager = seed_user(
                db, "Prototype Review Manager", "NONE", manager_token)
            reviewer = seed_user(
                db, "Prototype Review Customer", "NONE", reviewer_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,"
                "project_code_normalized,name,created_by) VALUES "
                "('PRTOWNER','prtowner','Prototype Owner project',%s) "
                "RETURNING project_id", (manager,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES "
                "(%s,'PRT','prt','Prototype') RETURNING department_id",
                (project,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,"
                "department_id,project_role) VALUES "
                "(%s,%s,%s,'PROJECT_MANAGER'),"
                "(%s,%s,%s,'CUSTOMER_MANAGER')",
                (project, manager, department,
                 project, reviewer, department),
            )
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.prt_prototypes(prototype_id,project_id,"
                    "name,created_by) VALUES (%s,%s,'Prototype',%s)",
                    (ids["prototype"], project, manager),
                )
                db.execute(
                    "INSERT INTO plm.prt_templates(prototype_template_id,"
                    "scope,project_id,name,current_template_version_ref,"
                    "created_by) VALUES (%s,'PROJECT',%s,'Template',%s,%s)",
                    (ids["template"], project, ids["template_version"], manager),
                )
                db.execute(
                    "INSERT INTO plm.prt_template_versions("
                    "prototype_template_version_id,prototype_template_id,"
                    "scope,project_id,version_no,content_fingerprint,"
                    "layout_contract,component_contract,applicable_terminals,"
                    "declared_artifact_count,created_by) VALUES "
                    "(%s,%s,'PROJECT',%s,1,%s,'{}','{}',"
                    "ARRAY['DESKTOP_WEB'],0,%s)",
                    (ids["template_version"], ids["template"], project,
                     b"t" * 32, manager),
                )
                db.execute(
                    "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                    "requirement_code,requirement_code_normalized,"
                    "current_approved_version_ref,created_by) VALUES "
                    "(%s,%s,'R-PRT','R-PRT',%s,%s)",
                    (ids["requirement"], project,
                     ids["requirement_version"], manager),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_versions("
                    "requirement_version_id,requirement_id,project_id,version_no,"
                    "version_state,statement,rationale,domain_name,priority,risk,"
                    "requirement_classification,content_fingerprint,"
                    "declared_source_count,declared_acceptance_count,"
                    "declared_capability_count,declared_assumption_count,"
                    "declared_exclusion_count,declared_dependency_count,"
                    "declared_ai_task_count,review_ref,review_round_ref,created_by) "
                    "VALUES (%s,%s,%s,1,'APPROVED','S','R','D','HIGH','LOW',"
                    "'STANDARD_FUNCTION',%s,1,0,0,0,0,0,0,%s,%s,%s)",
                    (ids["requirement_version"], ids["requirement"], project,
                     b"q" * 32, ids["requirement_review"],
                     ids["requirement_round"], manager),
                )
                db.execute(
                    "INSERT INTO plm.doc_file_objects(file_object_id,scope,"
                    "project_id,storage_class,storage_locator,"
                    "original_name_metadata,sha256,size_bytes,detected_mime,"
                    "file_state,available_at,created_by) VALUES "
                    "(%s,'PROJECT',%s,'PERSISTENT','prt/owner.pdf','owner.pdf',"
                    "%s,10,'application/pdf','AVAILABLE',"
                    "statement_timestamp(),%s)",
                    (ids["file"], project, b"d" * 32, manager),
                )
                db.execute(
                    "INSERT INTO plm.doc_documents(document_id,scope,project_id,"
                    "document_category,title,original_display_name,"
                    "document_state,created_by) VALUES "
                    "(%s,'PROJECT',%s,'REFERENCE_MATERIAL','Owner',"
                    "'owner.pdf','ACTIVE',%s)",
                    (ids["document"], project, manager),
                )
                db.execute(
                    "INSERT INTO plm.doc_document_versions(document_version_id,"
                    "document_id,scope,project_id,version_no,file_object_id,"
                    "content_sha256,size_bytes,detected_mime,"
                    "availability_state,created_by) VALUES "
                    "(%s,%s,'PROJECT',%s,1,%s,%s,10,'application/pdf',"
                    "'AVAILABLE',%s)",
                    (ids["document_version"], ids["document"], project,
                     ids["file"], b"d" * 32, manager),
                )

        templates = SqlAlchemyPrototypeVersionTemplateProof()
        requirements = SqlAlchemyPrototypeApprovedRequirementVersionProof()
        documents = SqlAlchemyPrototypeDocumentArtifactProof()
        current = PrototypeVersionCurrentValidator(
            templates=templates, requirements=requirements, documents=documents,
        )
        version_repository = SqlAlchemyPrototypeVersionCreateRepository()
        artifacts = (VersionArtifactRef(
            "DOCUMENT_VERSION", ids["document_version"]),)
        requirement_refs = (VersionRequirementRef(
            ids["requirement"], ids["requirement_version"]),)

        def create_version():
            with runtime.unit_of_work() as tx:
                template = templates.prove(
                    tx, project_id=project,
                    prototype_template_id=ids["template"],
                    prototype_template_version_id=ids["template_version"],
                )
                requirement = requirements.prove(
                    tx, project_id=project,
                    requirement_id=ids["requirement"],
                    requirement_version_id=ids["requirement_version"],
                )
                document = documents.prove_for_prototype_version(
                    tx, project_id=project,
                    document_version_id=ids["document_version"],
                )
                assert template and requirement and document
                payload = {
                    "project_id": str(project),
                    "prototype_id": str(ids["prototype"]),
                    "template_id": str(ids["template"]),
                    "template_version_id": str(ids["template_version"]),
                    "artifact_refs": [(
                        "DOCUMENT_VERSION", str(ids["document_version"]))],
                    "requirement_refs": [(
                        str(ids["requirement"]),
                        str(ids["requirement_version"]))],
                    "interaction_spec": {"interactions": []},
                    "coverage_summary": {"covered": 1},
                    "template_fingerprint": template.content_fingerprint,
                    "artifact_proofs": [(
                        "DOCUMENT_VERSION", str(ids["document_version"]),
                        document.content_sha256)],
                    "requirement_proofs": [(
                        str(ids["requirement"]),
                        str(ids["requirement_version"]),
                        requirement.content_fingerprint)],
                }
                view = version_repository.create(
                    tx, result_id=uuid.uuid4(), version_id=uuid.uuid4(),
                    project_id=project, prototype_id=ids["prototype"],
                    template_id=ids["template"],
                    template_version_id=ids["template_version"],
                    artifacts=artifacts, requirements=requirement_refs,
                    interaction={"interactions": []},
                    interaction_fingerprint=canonical_payload_fingerprint(
                        {"interactions": []}),
                    coverage={"covered": 1},
                    content_fingerprint=canonical_payload_fingerprint(payload),
                    actor_id=manager,
                )
                tx.commit()
                return view

        now = datetime.now(timezone.utc)
        audit = AuditService(SqlAlchemyAuditRepository())
        receipts = SqlAlchemyIdempotencyReceipts()
        access = SqlAlchemyReviewStartAccess()
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=project_repository,
        )
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        approval_trace = PrototypeApprovalTraceOwner(
            current=current, trace_links=SqlAlchemyTraceCreateRepository(),
            manifests=SqlAlchemyPrototypeApprovalTraceRepository(),
        )
        owner = PrototypeReviewSubjectOwner(
            repository=SqlAlchemyPrototypeReviewSubjectRepository(),
            reviewers=reviewers, current=current, audit=audit,
            approval_trace=approval_trace,
            clock=lambda: now,
        )
        guard = Guard()
        create_review = ReviewCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, license_guard=guard,
            repository=SqlAlchemyReviewCreationRepository(),
            receipts=receipts, audit=audit, subjects=owner,
            clock=lambda: now,
        )
        start_review = ReviewStartService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, reviewers=reviewers,
            license_guard=guard, repository=SqlAlchemyReviewStartRepository(),
            receipts=receipts, audit=audit, subjects=owner,
            clock=lambda: now,
        )
        transition = ReviewTransitionCommandService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, license_guard=guard,
            repository=SqlAlchemyReviewTransitionRepository(),
            receipts=receipts, audit=audit, subjects=owner,
            clock=lambda: now,
        )

        def create_start(version_id):
            created = create_review.create_idempotent(CreateReview(
                manager_token, CSRF, uuid.uuid4(), project, "PRT-03",
                ids["prototype"], version_id,
            ), idempotency_key=str(uuid.uuid4()))
            started = start_review.start_idempotent(StartReviewRound(
                manager_token, CSRF, project, created.review_id, version_id,
                (reviewer,), "PROTOTYPE_ALL_V1", 0, uuid.uuid4(),
            ), idempotency_key=str(uuid.uuid4()))
            return created.review_id, started.round_id

        first = create_version()
        review_one, round_one = create_start(first.prototype_version_id)
        first_approval = DecideReviewRound(
            reviewer_token, CSRF, project, review_one, round_one,
            uuid.uuid4(), ReviewDecisionKind.APPROVE, "Approved",
        )
        first_approval_key = str(uuid.uuid4())
        approved = transition.decide_idempotent(
            first_approval, idempotency_key=first_approval_key)
        assert approved.state.value == "APPROVED"
        replayed = transition.decide_idempotent(
            first_approval, idempotency_key=first_approval_key)
        assert replayed == approved

        second = create_version()
        review_two, round_two = create_start(second.prototype_version_id)
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.doc_file_objects SET file_state='RESTRICTED' "
                "WHERE file_object_id=%s", (ids["file"],),
            )
        try:
            transition.decide_idempotent(DecideReviewRound(
                reviewer_token, CSRF, project, review_two, round_two,
                uuid.uuid4(), ReviewDecisionKind.APPROVE, "Stale",
            ), idempotency_key=str(uuid.uuid4()))
        except ReviewTransitionCommandError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else:
            raise AssertionError("input drift must block approval")
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.doc_file_objects SET file_state='AVAILABLE' "
                "WHERE file_object_id=%s", (ids["file"],),
            )
        approved = transition.decide_idempotent(DecideReviewRound(
            reviewer_token, CSRF, project, review_two, round_two,
            uuid.uuid4(), ReviewDecisionKind.APPROVE, "Approved after restore",
        ), idempotency_key=str(uuid.uuid4()))
        assert approved.state.value == "APPROVED"

        third = create_version()
        review_three, round_three = create_start(third.prototype_version_id)
        withdrawn = transition.withdraw_idempotent(WithdrawReviewRound(
            manager_token, CSRF, project, review_three, round_three,
            uuid.uuid4(), 1, "Scope changed",
        ), idempotency_key=str(uuid.uuid4()))
        assert withdrawn.state.value == "WITHDRAWN"
        with connect(database) as db:
            pointer, lock_version = db.execute(
                "SELECT current_approved_version_ref,lock_version FROM "
                "plm.prt_prototypes WHERE prototype_id=%s",
                (ids["prototype"],),
            ).fetchone()
            states = db.execute(
                "SELECT version_no,version_state FROM "
                "plm.prt_prototype_versions WHERE prototype_id=%s "
                "ORDER BY version_no", (ids["prototype"],),
            ).fetchall()
            assert pointer == second.prototype_version_id
            assert lock_version == 6
            assert states == [
                (1, "SUPERSEDED"), (2, "APPROVED"), (3, "RETURNED")]
            assert db.execute(
                "SELECT count(*) FROM plm.prt_version_review_state_results "
                "WHERE prototype_id=%s", (ids["prototype"],),
            ).fetchone()[0] == 6
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action IN "
                "('PROTOTYPE_VERSION_APPROVED',"
                "'PROTOTYPE_VERSION_WITHDRAWN')",
            ).fetchone()[0] == 3
            assert db.execute(
                "SELECT count(*) FROM "
                "plm.prt_version_approval_trace_manifests WHERE "
                "prototype_id=%s", (ids["prototype"],),
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.prt_version_approval_trace_sources s "
                "JOIN plm.prt_version_approval_trace_manifests m ON "
                "m.approval_trace_manifest_id=s.approval_trace_manifest_id "
                "WHERE m.prototype_id=%s", (ids["prototype"],),
            ).fetchone()[0] == 6
            assert db.execute(
                "SELECT s.source_kind,s.source_owner_module,s.source_object_type,"
                "s.relation_type,count(*) FROM "
                "plm.prt_version_approval_trace_sources s JOIN "
                "plm.prt_version_approval_trace_manifests m ON "
                "m.approval_trace_manifest_id=s.approval_trace_manifest_id "
                "WHERE m.prototype_id=%s GROUP BY 1,2,3,4 ORDER BY 1",
                (ids["prototype"],),
            ).fetchall() == [
                ("DOCUMENT_VERSION", "document", "DOC-02", "DERIVED_FROM", 2),
                ("REQUIREMENT_VERSION", "requirement", "REQ-03", "IMPLEMENTS", 2),
                ("TEMPLATE_VERSION", "prototype", "PRT-04", "DERIVED_FROM", 2),
            ]
            assert db.execute(
                "SELECT count(*) FROM "
                "plm.prt_version_approval_trace_manifests m JOIN "
                "plm.prt_version_review_state_results r ON "
                "r.review_state_result_id=m.review_state_result_id "
                "WHERE r.event_type<>'APPROVED'",
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.trc_links WHERE link_state='ACTIVE' "
                "AND target_owner_module='prototype' "
                "AND target_object_type='PRT-03' AND target_object_id=%s",
                (ids["prototype"],),
            ).fetchone()[0] == 6

        class FailingTraceLinks:
            def create_active(self, transaction, *, edge, actor_id, trace_id):
                raise RuntimeError("synthetic Trace persistence failure")

        failing_trace = PrototypeApprovalTraceOwner(
            current=current, trace_links=FailingTraceLinks(),
            manifests=SqlAlchemyPrototypeApprovalTraceRepository(),
        )
        failing_owner = PrototypeReviewSubjectOwner(
            repository=SqlAlchemyPrototypeReviewSubjectRepository(),
            reviewers=reviewers, current=current, audit=audit,
            approval_trace=failing_trace, clock=lambda: now,
        )
        failing_transition = ReviewTransitionCommandService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, license_guard=guard,
            repository=SqlAlchemyReviewTransitionRepository(),
            receipts=receipts, audit=audit, subjects=failing_owner,
            clock=lambda: now,
        )
        fourth = create_version()
        review_four, round_four = create_start(fourth.prototype_version_id)
        failed_key = str(uuid.uuid4())
        try:
            failing_transition.decide_idempotent(DecideReviewRound(
                reviewer_token, CSRF, project, review_four, round_four,
                uuid.uuid4(), ReviewDecisionKind.APPROVE,
                "Trace failure must roll back",
            ), idempotency_key=failed_key)
        except ReviewTransitionCommandError as error:
            assert error.code == "REVIEW_UNAVAILABLE", error.code
        else:
            raise AssertionError("Trace persistence failure must reject approval")
        with connect(database) as db:
            assert db.execute(
                "SELECT current_approved_version_ref,lock_version FROM "
                "plm.prt_prototypes WHERE prototype_id=%s",
                (ids["prototype"],),
            ).fetchone() == (second.prototype_version_id, 7)
            assert db.execute(
                "SELECT version_state,review_ref,review_round_ref FROM "
                "plm.prt_prototype_versions WHERE prototype_version_id=%s",
                (fourth.prototype_version_id,),
            ).fetchone() == ("IN_REVIEW", review_four, round_four)
            assert db.execute(
                "SELECT review_state,active_round_id,lock_version FROM "
                "plm.rvw_reviews WHERE review_id=%s", (review_four,),
            ).fetchone() == ("IN_REVIEW", round_four, 1)
            assert db.execute(
                "SELECT round_state,lock_version FROM plm.rvw_review_rounds "
                "WHERE review_round_id=%s", (round_four,),
            ).fetchone() == ("IN_REVIEW", 0)
            assert db.execute(
                "SELECT count(*) FROM plm.prt_version_review_state_results "
                "WHERE prototype_version_id=%s AND event_type='APPROVED'",
                (fourth.prototype_version_id,),
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM "
                "plm.prt_version_approval_trace_manifests WHERE "
                "prototype_version_id=%s", (fourth.prototype_version_id,),
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.trc_links WHERE link_state='ACTIVE' "
                "AND target_version_id=%s", (fourth.prototype_version_id,),
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation='V1_REVIEW_DECIDE' AND key_digest=%s",
                (hashlib.sha256(failed_key.encode("ascii")).digest(),),
            ).fetchone()[0] == 0
        if verify_submission:
            recovered = transition.decide_idempotent(DecideReviewRound(
                reviewer_token, CSRF, project, review_four, round_four,
                uuid.uuid4(), ReviewDecisionKind.APPROVE,
                "Approve after rollback proof",
            ), idempotency_key=str(uuid.uuid4()))
            assert recovered.state.value == "APPROVED"

            fifth = create_version()
            submission = PrototypeReviewSubmissionService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=guard, authorization=authorization,
                reviewers=reviewers, receipts=receipts,
                replay_repository=(
                    SqlAlchemyProjectReviewSubmissionRepository()),
                reviews=ProjectReviewPersistenceService(
                    creation_repository=SqlAlchemyReviewCreationRepository(),
                    round_repository=SqlAlchemyReviewStartRepository(),
                    audit=audit, subjects=owner, clock=lambda: now,
                ),
                subjects=owner, clock=lambda: now,
            )
            submission_key = str(uuid.uuid4())
            submit_command = SubmitPrototypeVersionReview(
                manager_token, CSRF, uuid.uuid4(), project,
                ids["prototype"], fifth.prototype_version_id,
                (reviewer,), "PROTOTYPE_ALL_V1", submission_key,
            )
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.doc_file_objects SET file_state='RESTRICTED' "
                    "WHERE file_object_id=%s", (ids["file"],),
                )
            try:
                submission.submit(submit_command)
            except PrototypeReviewSubmissionError as error:
                assert error.code == "BUSINESS_REVIEW_NOT_ELIGIBLE", error.code
            else:
                raise AssertionError("current input drift must block submission")
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.rvw_reviews WHERE "
                    "subject_type='PRT-03' AND subject_id=%s AND "
                    "review_state='IN_REVIEW'", (ids["prototype"],),
                ).fetchone()[0] == 0
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                    "operation='V1_PRT_VERSION_SUBMIT_REVIEW' AND "
                    "key_digest=%s", (hashlib.sha256(
                        submission_key.encode("ascii")).digest(),),
                ).fetchone()[0] == 0
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.doc_file_objects SET file_state='AVAILABLE' "
                    "WHERE file_object_id=%s", (ids["file"],),
                )
            submitted = submission.submit(submit_command)
            replayed_submission = submission.submit(submit_command)
            assert replayed_submission == submitted
            try:
                submission.submit(SubmitPrototypeVersionReview(
                    manager_token, CSRF, uuid.uuid4(), project,
                    ids["prototype"], fifth.prototype_version_id,
                    (manager, reviewer), "PROTOTYPE_ALL_V1", submission_key,
                ))
            except PrototypeReviewSubmissionError as error:
                assert error.code == "CONFLICT_IDEMPOTENCY", error.code
            else:
                raise AssertionError("changed payload must conflict")
            try:
                submission.submit(SubmitPrototypeVersionReview(
                    reviewer_token, CSRF, uuid.uuid4(), project,
                    ids["prototype"], fifth.prototype_version_id,
                    (reviewer,), "PROTOTYPE_ALL_V1", str(uuid.uuid4()),
                ))
            except PrototypeReviewSubmissionError as error:
                assert error.code == "RESOURCE_NOT_FOUND", error.code
            else:
                raise AssertionError("CustomerManager must not submit Review")
            guard.enabled = False
            try:
                submission.submit(SubmitPrototypeVersionReview(
                    manager_token, CSRF, uuid.uuid4(), project,
                    ids["prototype"], fifth.prototype_version_id,
                    (reviewer,), "PROTOTYPE_ALL_V1", str(uuid.uuid4()),
                ))
            except PrototypeReviewSubmissionError as error:
                assert error.code == "LICENSE_OPERATION_DENIED", error.code
            else:
                raise AssertionError("invalid License must block submission")
            finally:
                guard.enabled = True
            with connect(database) as db:
                assert db.execute(
                    "SELECT version_state,review_ref,review_round_ref FROM "
                    "plm.prt_prototype_versions WHERE "
                    "prototype_version_id=%s", (fifth.prototype_version_id,),
                ).fetchone() == (
                    "IN_REVIEW", submitted.review_id, submitted.round_id)
                assert db.execute(
                    "SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s "
                    "AND review_state='IN_REVIEW' AND active_round_id=%s",
                    (submitted.review_id, submitted.round_id),
                ).fetchone()[0] == 1
                assert db.execute(
                    "SELECT count(*) FROM plm.rvw_review_rounds WHERE "
                    "review_round_id=%s AND round_state='IN_REVIEW'",
                    (submitted.round_id,),
                ).fetchone()[0] == 1
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                    "operation='V1_PRT_VERSION_SUBMIT_REVIEW' AND "
                    "key_digest=%s AND result_ref_type="
                    "'V1_PRT_VERSION_REVIEW_SUBMISSION'",
                    (hashlib.sha256(
                        submission_key.encode("ascii")).digest(),),
                ).fetchone()[0] == 1
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE "
                    "target_object_id IN (%s,%s) AND action IN "
                    "('REVIEW_CREATED','REVIEW_STARTED')",
                    (submitted.review_id, submitted.round_id),
                ).fetchone()[0] == 2
        command.check(cfg)
        print(
            "PRT_01_A07_A02_P02_REVIEW_OWNER_PASS: real PROJECT Review "
            "create/start/approve/withdraw, current input drift fence, "
            "approval Trace failure rollback, supersede, pointer "
            "preservation, immutable results and audit verified on "
            "PostgreSQL 18"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
