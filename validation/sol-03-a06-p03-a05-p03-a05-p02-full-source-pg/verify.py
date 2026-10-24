"""Same-disposable-PG qualified Requirement and approved Section for Outline."""

from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_version_create_router,
    create_windows_outline_version_validate_router,
    create_windows_section_review_submission_router,
    create_windows_section_version_create_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
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
from plm_assistant.modules.capability.infrastructure.requirement_source_proof import (
    SqlAlchemyCapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import (
    SqlAlchemyEvidenceRequirementSourceProof,
)
from plm_assistant.modules.handover.infrastructure.requirement_source_proof import (
    SqlAlchemyHandoverRequirementSourceProof,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
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
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, RequirementAcceptanceDraft,
    RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
    RequirementVersionCreateService,
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
from plm_assistant.modules.requirement.infrastructure.human_decision_source_proof import (
    SqlAlchemyRequirementHumanDecisionSourceProof,
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
from plm_assistant.modules.survey.infrastructure.requirement_source_proof import (
    SqlAlchemySurveyConclusionRequirementSourceProof,
)
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "section_terminal_for_qualified_outline",
    ROOT / "validation/sol-05-a04-p13-p06-p01-section-terminal-windows/verify.py",
)
assert spec is not None and spec.loader is not None
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)
original_terminal = terminal._terminal


def _connection(port: int) -> dict[str, object]:
    return dict(host="127.0.0.1", port=port, user="poc_admin", dbname="postgres")


def _seed_capability(port: int, actor: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Synthetic GLOBAL standard fact, matching the existing Requirement PG fixture."""
    ids = {name: uuid.uuid4() for name in (
        "file", "document", "document_version", "evidence", "baseline",
        "baseline_version", "item_row", "item", "review", "round", "snapshot",
    )}
    with psycopg.connect(**_connection(port)) as db, db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,"
            "storage_class,storage_locator,original_name_metadata,sha256,"
            "size_bytes,detected_mime,file_state,created_by,available_at) "
            "VALUES (%s,'GLOBAL','PERSISTENT','global/objects/aa/'||%s,"
            "'synthetic-standard.pdf',%s,16,'application/pdf','AVAILABLE',"
            "%s,statement_timestamp())",
            (ids["file"], ids["file"].hex, b"g" * 32, actor),
        )
        db.execute(
            "INSERT INTO plm.doc_documents(document_id,scope,document_category,"
            "title,original_display_name,document_state,created_by) "
            "VALUES (%s,'GLOBAL','TEMPLATE','Synthetic standard',"
            "'synthetic-standard.pdf','ACTIVE',%s)",
            (ids["document"], actor),
        )
        db.execute(
            "INSERT INTO plm.doc_document_versions(document_version_id,"
            "document_id,scope,version_no,file_object_id,content_sha256,"
            "size_bytes,detected_mime,source_metadata,created_by,"
            "availability_state,integrity_checked_at) "
            "VALUES (%s,%s,'GLOBAL',1,%s,%s,16,'application/pdf','{}'::jsonb,"
            "%s,'AVAILABLE',statement_timestamp())",
            (ids["document_version"], ids["document"], ids["file"],
             b"g" * 32, actor),
        )
        db.execute(
            "INSERT INTO plm.evd_evidence_records(evidence_id,scope,"
            "document_id,document_version_id,locator_type,"
            "locator_schema_version,locator_payload,content_fingerprint,"
            "display_label,eligibility_state,eligibility_reason,created_by) "
            "VALUES (%s,'GLOBAL',%s,%s,'DOCUMENT',1,"
            "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,"
            "'Synthetic standard evidence','ELIGIBLE','Test fixture',%s)",
            (ids["evidence"], ids["document"], ids["document_version"],
             b"g" * 32, actor),
        )
        source = "sha256:" + "a" * 64
        db.execute(
            "INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,"
            "baseline_state,source_collection_ref,current_approved_version_ref,"
            "created_by) VALUES (%s,'OUTLINE.STANDARD','Synthetic standard',"
            "'ACTIVE',%s,%s,%s)",
            (ids["baseline"], source, ids["baseline_version"], actor),
        )
        db.execute(
            "INSERT INTO plm.cap_baseline_versions(baseline_version_id,"
            "baseline_id,version_no,version_state,source_collection_ref,"
            "content_fingerprint,declared_item_count,declared_document_ref_count,"
            "declared_evidence_ref_count,review_ref,review_round_ref,created_by) "
            "VALUES (%s,%s,1,'APPROVED',%s,%s,1,1,1,%s,%s,%s)",
            (ids["baseline_version"], ids["baseline"], source, b"c" * 32,
             ids["review"], ids["round"], actor),
        )
        db.execute(
            "INSERT INTO plm.cap_items(capability_item_row_id,"
            "baseline_version_id,baseline_id,capability_item_id,ordinal,"
            "capability_code,domain_name,module_name,feature_name,name,"
            "description,boundary_text,item_state) VALUES "
            "(%s,%s,%s,%s,0,'OUTLINE.STANDARD.ITEM','PLM','Solution',"
            "'Outline','Synthetic standard','Test capability',"
            "'Test only','AVAILABLE')",
            (ids["item_row"], ids["baseline_version"],
             ids["baseline"], ids["item"]),
        )
        db.execute(
            "INSERT INTO plm.rvw_reviews(review_id,scope,subject_type,"
            "subject_id,policy_code,review_state,active_round_id,"
            "lock_version,created_by) VALUES (%s,'GLOBAL','CAP-01',%s,"
            "'DEPLOYMENT_ALL_V1','APPROVED',NULL,2,%s)",
            (ids["review"], ids["baseline"], actor),
        )
        db.execute(
            "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,"
            "scope,round_no,subject_version_id,round_state,lock_version,"
            "started_by,started_at) VALUES (%s,%s,'GLOBAL',1,%s,'APPROVED',1,"
            "%s,statement_timestamp())",
            (ids["round"], ids["review"], ids["baseline_version"], actor),
        )
        db.execute(
            "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,"
            "review_round_id,scope,subject_type,subject_id,subject_version_id,"
            "content_fingerprint,proof_schema_version,verified_at) VALUES "
            "(%s,%s,%s,'GLOBAL','CAP-01',%s,%s,%s,1,statement_timestamp())",
            (ids["snapshot"], ids["review"], ids["round"],
             ids["baseline"], ids["baseline_version"], b"c" * 32),
        )
    return ids["baseline_version"], ids["item"], ids["evidence"]


def _approved_requirement_v2(**context) -> tuple[uuid.UUID, uuid.UUID, bytes, bytes]:
    """Replace the abbreviated historical v1 only by a real new version."""
    project, port = context["project"], context["port"]
    with psycopg.connect(**_connection(port)) as db:
        requirement, old_version, evidence = db.execute(
            "SELECT r.requirement_id,r.requirement_version_id,e.evidence_id "
            "FROM plm.sol_section_versions v "
            "JOIN plm.sol_section_requirement_refs r ON "
            "r.solution_section_version_id=v.solution_section_version_id "
            "JOIN plm.sol_section_evidence_refs e ON "
            "e.solution_section_version_id=v.solution_section_version_id "
            "WHERE v.project_id=%s AND v.version_state='APPROVED' LIMIT 1",
            (project,),
        ).fetchone()
        lock_version = db.execute(
            "SELECT lock_version FROM plm.req_requirements "
            "WHERE requirement_id=%s", (requirement,),
        ).fetchone()[0]
        reviewer = db.execute(
            "SELECT user_id FROM plm.prj_project_members WHERE project_id=%s "
            "AND project_role='CUSTOMER_MEMBER' AND state='ACTIVE' LIMIT 1",
            (project,),
        ).fetchone()[0]
    runtime, token, csrf, guard, audit = (context[name] for name in (
        "runtime", "token", "csrf", "license_guard", "audit"))
    # The inherited synthetic v1 declared one source but never seeded its row.
    # Close that fixture-only count before the real v2 approval supersedes v1.
    old_source = uuid.uuid4()
    with psycopg.connect(**_connection(port)) as db, db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        assert db.execute(
            "SELECT count(*) FROM plm.req_sources WHERE requirement_version_id=%s",
            (old_version,),
        ).fetchone()[0] == 0
        db.execute(
            "INSERT INTO plm.req_sources(requirement_source_id,"
            "requirement_version_id,requirement_id,project_id,ordinal,"
            "source_type,source_object_id) VALUES "
            "(%s,%s,%s,%s,0,'PROJECT_EVIDENCE',%s)",
            (old_source, old_version, requirement, project, evidence),
        )
        db.execute(
            "INSERT INTO plm.req_source_evidence_refs(requirement_source_id,"
            "requirement_version_id,requirement_id,project_id,evidence_id,"
            "ordinal) VALUES (%s,%s,%s,%s,%s,0)",
            (old_source, old_version, requirement, project, evidence),
        )
    baseline_version, capability_item, standard_evidence = _seed_capability(
        port, context["manager"])
    reviewer_token, reviewer_csrf = uuid.uuid4().bytes * 2, uuid.uuid4().bytes * 2
    with psycopg.connect(**_connection(port)) as db, db.transaction():
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,"
            "user_id,credential_version,idle_expires_at,absolute_expires_at) "
            "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
            "statement_timestamp()+interval '1 hour')",
            (hashlib.sha256(reviewer_token).digest(),
             hashlib.sha256(reviewer_csrf).digest(), reviewer),
        )
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    evidence_proof = SqlAlchemyEvidenceRequirementSourceProof()
    capability_proof = SqlAlchemyCapabilityRequirementSourceProof()
    fixed_evidence = SqlAlchemyEvidenceFixedSourceRepository()
    decisions = SqlAlchemyRequirementHumanDecisionSourceProof()
    current = RequirementVersionCurrentValidator(
        survey_sources=SqlAlchemySurveyConclusionRequirementSourceProof(),
        handover_sources=SqlAlchemyHandoverRequirementSourceProof(),
        human_decisions=decisions, project_evidence=evidence_proof,
        capability_sources=capability_proof, fixed_evidence=fixed_evidence,
    )
    receipts = SqlAlchemyIdempotencyReceipts()
    created = RequirementVersionCreateService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
        authorization=authorization,
        repository=SqlAlchemyRequirementVersionCreateRepository(),
        receipts=receipts, audit=audit,
        survey_sources=SqlAlchemySurveyConclusionRequirementSourceProof(),
        handover_sources=SqlAlchemyHandoverRequirementSourceProof(),
        human_decisions=decisions, project_evidence=evidence_proof,
        capability_sources=capability_proof, fixed_evidence=fixed_evidence,
    ).create(CreateRequirementVersion(
        session_token=token, csrf_token=csrf, trace_id=uuid.uuid4(),
        project_id=project, requirement_id=requirement,
        expected_lock_version=lock_version, initial=False,
        base_version_ref=old_version,
        title="Qualified requirement for Outline proof",
        statement="Synthetic implementation requirement",
        rationale="Synthetic same-database current qualification",
        domain_name="PLM", priority="HIGH", risk="MEDIUM",
        classification="STANDARD_FUNCTION",
        sources=(RequirementSourceDraft(
            "PROJECT_EVIDENCE", evidence, None, (evidence,)),),
        acceptance_criteria=(RequirementAcceptanceDraft(
            "Observable result", "Run acceptance test", "Project data",
            "Windows 11", "Synthetic acceptance report"),),
        capability_assessments=(RequirementCapabilityAssessmentDraft(
            baseline_version, capability_item, "DIRECT", "Covered",
            "Use standard configuration", "HUMAN", "CONFIRMED",
            (RequirementAssessmentEvidenceDraft(
                standard_evidence, "STANDARD"),
             RequirementAssessmentEvidenceDraft(evidence, "PROJECT")),
        ),), assumptions=(), exclusions=(),
        dependencies=(), client_reason="Create complete test version",
        idempotency_key="outline-qualified-req-v2-0001",
    ))
    reviewers = ProjectReviewerQualificationService(
        users=SqlAlchemyReviewUserAccess(),
        projects=SqlAlchemyProjectAuthorizationRepository())
    owner = RequirementReviewSubjectOwner(
        repository=SqlAlchemyRequirementReviewSubjectRepository(),
        reviewers=reviewers, current=current, audit=audit)
    submission = RequirementReviewSubmissionService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
        authorization=authorization, reviewers=reviewers, receipts=receipts,
        replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
        reviews=ProjectReviewPersistenceService(
            creation_repository=SqlAlchemyReviewCreationRepository(),
            round_repository=SqlAlchemyReviewStartRepository(),
            audit=audit, subjects=owner), subjects=owner,
    ).submit(SubmitRequirementVersionReview(
        token, csrf, uuid.uuid4(), project, requirement,
        created.requirement_version_id, (reviewer,),
        "REQUIREMENT_ALL_V1", "outline-qualified-req-review-0001",
    ))
    transition = ReviewTransitionCommandService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyReviewStartAccess(), projects=authorization,
        license_guard=guard,
        repository=SqlAlchemyReviewTransitionRepository(),
        receipts=receipts, audit=audit,
        subjects=ProjectReviewSubjectRegistry((owner,)),
    )
    approval = transition.decide_idempotent(DecideReviewRound(
        reviewer_token, reviewer_csrf, project, submission.review_id,
        submission.round_id, uuid.uuid4(), ReviewDecisionKind.APPROVE,
    ), idempotency_key="outline-qualified-req-approve-0001")
    assert approval.state.value == "APPROVED"
    print("OUTLINE_QUALIFIED_REQUIREMENT_V2_PASS")
    return requirement, created.requirement_version_id, reviewer_token, reviewer_csrf


def _headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def _approved_section_v2(**context) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    project, port = context["project"], context["port"]
    requirement, requirement_version, reviewer_token, reviewer_csrf = (
        _approved_requirement_v2(**context))
    with psycopg.connect(**_connection(port)) as db:
        outline, section, old_version = db.execute(
            "SELECT s.solution_outline_id,s.solution_section_id,"
            "s.current_approved_version_ref FROM plm.sol_sections s "
            "WHERE s.project_id=%s AND s.current_approved_version_ref IS NOT NULL "
            "LIMIT 1", (project,),
        ).fetchone()
    with context["runtime"].unit_of_work() as tx:
        old = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project, section_id=section, version_id=old_version)
        assert old is not None and old.version_state == "APPROVED"
        assert old.spec_binding_state == "FIXED_REFS"
    payload = {
        "title": "Qualified solution section for Outline proof",
        "content_document_version_ref": str(old.content_document_version_ref),
        "content_artifact_ref": None,
        "requirement_refs": [{
            "requirement_id": str(requirement),
            "requirement_version_id": str(requirement_version),
        }],
        "evidence_ids": [str(item) for item in old.evidence_ids],
        "assumptions": list(old.assumptions),
        "exclusions": list(old.exclusions),
        "spec_binding_state": "NONE_REQUIRED",
        "spec_not_required_reason": (
            "Synthetic standard-function Section needs no specialist specification"),
        "structured_spec_refs": [],
    }
    runtime, token, csrf, guard, audit = (context[name] for name in (
        "runtime", "token", "csrf", "license_guard", "audit"))
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    create_router = create_windows_section_version_create_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit,
        documents=context["documents"], downloads=context["downloads"],
        parse_results=context["parse_results"])
    create_path = f"/api/v1/projects/{project}/solution-sections/{section}/versions"
    with TestClient(create_app(solution_section_version_create_router=create_router),
                    base_url="https://plm.example.test") as app:
        response = app.post(create_path, headers=_headers(
            token, csrf, "outline-full-section-v2-create-0001"), json=payload)
        assert response.status_code == 201, response.text
        version = uuid.UUID(response.json()["data"]["solution_section_version_id"])
    creator, _ = terminal.prior._trace_services(
        runtime=runtime, license_guard=guard, audit=audit)
    creator.create_refs(terminal.prior.CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project,
        terminal.prior.TraceResourceVersionRef(
            "REQ-03", requirement, requirement_version),
        terminal.prior.TraceResourceVersionRef("SOL-05", section, version),
        "IMPLEMENTS"), idempotency_key="outline-full-section-v2-trace-0001")
    submit_router = create_windows_section_review_submission_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit,
        documents=context["documents"], downloads=context["downloads"],
        parse_results=context["parse_results"])
    with psycopg.connect(**_connection(port)) as db:
        reviewer = db.execute(
            "SELECT user_id FROM plm.prj_project_members WHERE project_id=%s "
            "AND project_role='CUSTOMER_MEMBER' AND state='ACTIVE' LIMIT 1",
            (project,),
        ).fetchone()[0]
    submit_path = f"{create_path}/{version}:submit-review"
    with TestClient(create_app(
            solution_section_review_submission_router=submit_router),
            base_url="https://plm.example.test") as app:
        response = app.post(submit_path, headers=_headers(
            token, csrf, "outline-full-section-v2-submit-0001"), json={
                "reviewer_ids": [str(reviewer)],
                "policy_ref": "SOLUTION_SECTION_ALL_V1",
                "due_at": None, "submission_note": None,
            })
        assert response.status_code == 201, response.text
    with psycopg.connect(**_connection(port)) as db:
        review_id, round_id = db.execute(
            "SELECT review_ref,review_round_ref FROM plm.sol_section_versions "
            "WHERE solution_section_version_id=%s", (version,),
        ).fetchone()
    review_router = create_windows_project_review_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit,
        documents=context["documents"], downloads=context["downloads"],
        parse_results=context["parse_results"])
    review_path = (f"/api/v1/projects/{project}/reviews/{review_id}/rounds/"
                   f"{round_id}:decide")
    with TestClient(create_app(review_command_router=review_router),
                    base_url="https://plm.example.test") as app:
        response = app.post(review_path, headers=_headers(
            reviewer_token, reviewer_csrf,
            "outline-full-section-v2-approve-0001"), json={
                "decision": "APPROVE", "comment": None,
            })
        assert response.status_code == 200, response.text
    with psycopg.connect(**_connection(port)) as db:
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.sol_sections "
            "WHERE solution_section_id=%s", (section,),
        ).fetchone()[0] == version
    print("OUTLINE_QUALIFIED_SECTION_V2_PASS")
    return outline, section, requirement, requirement_version


def _outline_full(**context) -> None:
    outline, section, requirement, requirement_version = _approved_section_v2(
        **context)
    project, port = context["project"], context["port"]
    runtime, token, csrf, guard, audit = (context[name] for name in (
        "runtime", "token", "csrf", "license_guard", "audit"))
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    with tempfile.TemporaryDirectory(prefix="plm-outline-full-pg-") as path_root:
        storage_root = Path(path_root)
        create_router = create_windows_outline_version_create_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit,
            document_storage_root=storage_root,
            parse_result_storage_root=storage_root)
        validate_router = create_windows_outline_version_validate_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit,
            document_storage_root=storage_root,
            parse_result_storage_root=storage_root,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"])
        path = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
        payload = {
            "section_ids": [str(section)],
            "requirement_refs": [{
                "requirement_id": str(requirement),
                "requirement_version_id": str(requirement_version),
            }],
            "reference_refs": [], "missing_declarations": [],
            "conflict_declarations": [],
        }
        with TestClient(create_app(
                solution_outline_version_create_router=create_router,
                solution_outline_version_validate_router=validate_router),
                base_url="https://plm.example.test") as app:
            created = app.post(path, headers=_headers(
                token, csrf, "outline-full-pg-create-0001"), json=payload)
            assert created.status_code == 201, created.text
            version = uuid.UUID(
                created.json()["data"]["solution_outline_version_id"])
            validate_path = f"{path}/{version}:validate"
            first = app.post(validate_path, headers=_headers(
                token, csrf, "outline-full-pg-validate-0001"))
            assert first.status_code == 200, first.text
            data = first.json()["data"]
            print("OUTLINE_FULL_FACTS", data["facts"])
            assert data["facts"] == {
                "order": "PASS", "source": "PASS", "coverage": "PASS"}, data
            assert data["ready_for_review"] is True
            replay = app.post(validate_path, headers=_headers(
                token, csrf, "outline-full-pg-validate-0001"))
            assert replay.status_code == 200 and replay.json()["data"] == data
            with ThreadPoolExecutor(max_workers=2) as workers:
                competing = tuple(workers.map(
                    lambda _: app.post(validate_path, headers=_headers(
                        token, csrf, "outline-full-pg-race-0001")), range(2)))
            assert all(item.status_code == 200 for item in competing), competing
            assert competing[0].json()["data"] == competing[1].json()["data"]
            assert competing[0].json()["data"]["facts"] == data["facts"]
            with psycopg.connect(**_connection(port)) as db:
                section_version = db.execute(
                    "SELECT current_approved_version_ref FROM plm.sol_sections "
                    "WHERE solution_section_id=%s", (section,),
                ).fetchone()[0]
                edge = db.execute(
                    "SELECT trace_link_id FROM plm.trc_links WHERE project_id=%s "
                    "AND target_object_id=%s AND target_version_id=%s "
                    "AND link_state='ACTIVE' AND relation_type='IMPLEMENTS'",
                    (project, section, section_version),
                ).fetchone()[0]
            _, revoker = terminal.prior._trace_services(
                runtime=runtime, license_guard=guard, audit=audit)
            revoker.revoke(terminal.prior.RevokeTraceLink(
                token, csrf, uuid.uuid4(), project, edge, 0),
                idempotency_key="outline-full-pg-revoke-0001")
            gap = app.post(validate_path, headers=_headers(
                token, csrf, "outline-full-pg-validate-gap-0001"))
            assert gap.status_code == 200, gap.text
            print("OUTLINE_GAP_FACTS", gap.json()["data"]["facts"])
            assert gap.json()["data"]["facts"]["coverage"] != "PASS"
            assert gap.json()["data"]["ready_for_review"] is False
            race_replay = app.post(validate_path, headers=_headers(
                token, csrf, "outline-full-pg-validate-0001"))
            assert race_replay.status_code == 200
            assert race_replay.json()["data"] == data
    with psycopg.connect(**_connection(port)) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_OUTLINE_VERSION_VALIDATED' AND target_version_id=%s",
            (version,),
        ).fetchone()[0] == 3
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_OUTLINE_VERSION_VALIDATE'",
        ).fetchone()[0] == 3
    print("SOL_03_A06_P03_A05_P03_A05_P02_FULL_SOURCE_PG_PASS")


if __name__ == "__main__":
    def hooked(case: str, **context):
        assert case == "APPROVE"
        original_terminal(case, **context)
        _outline_full(**context)
    terminal._terminal = hooked
    terminal._run("APPROVE")
