"""Isolated PG/HTTP proof of a genuinely approved Prototype scope."""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import math
import runpy
import shutil
import socket
import statistics
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy import event

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    create_windows_workflow_checklist_qualification_router,
    create_windows_workflow_checklist_record_router,
    create_windows_workflow_stage_transition_router,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import SqlAlchemyPrototypeDocumentArtifactProof
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.database import (
    DatabaseEngineOptions, create_database_runtime,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.prototype.application.approval_trace import PrototypeApprovalTraceOwner
from plm_assistant.modules.prototype.application.create_identity import CreatePrototypeIdentity, PrototypeIdentityCreateService
from plm_assistant.modules.prototype.application.create_version import (
    CreatePrototypeVersion, PrototypeVersionCreateService, VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.current_version import PrototypeVersionCurrentValidator
from plm_assistant.modules.prototype.application.mark_not_required import (
    MarkPrototypeNotRequired, PrototypeScopeDecisionService,
)
from plm_assistant.modules.prototype.application.requirement_links import (
    CreateRequirementPrototypeLink, RequirementPrototypeCoverage,
    RequirementPrototypeLinkError, RequirementPrototypeLinkService,
    SupersedeRequirementPrototypeLink,
    UncoveredAcceptanceCriterion,
)
from plm_assistant.modules.prototype.application.review_subject import PrototypeReviewSubjectOwner
from plm_assistant.modules.prototype.application.submit_review import (
    PrototypeReviewSubmissionService, SubmitPrototypeVersionReview,
)
from plm_assistant.modules.prototype.infrastructure.approval_trace_repository import SqlAlchemyPrototypeApprovalTraceRepository
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import SqlAlchemyPrototypeIdentityCreateRepository
from plm_assistant.modules.prototype.infrastructure.requirement_link_repository import SqlAlchemyRequirementPrototypeLinkRepository
from plm_assistant.modules.prototype.infrastructure.review_subject_repository import SqlAlchemyPrototypeReviewSubjectRepository
from plm_assistant.modules.prototype.infrastructure.scope_decision_repository import SqlAlchemyPrototypeScopeDecisionRepository
from plm_assistant.modules.prototype.infrastructure.version_create_repository import SqlAlchemyPrototypeVersionCreateRepository
from plm_assistant.modules.prototype.infrastructure.version_input_proofs import SqlAlchemyPrototypeVersionTemplateProof
from plm_assistant.modules.prototype.infrastructure.version_read_repository import SqlAlchemyPrototypeVersionReadRepository
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.review.application.project_persistence import ProjectReviewPersistenceService
from plm_assistant.modules.review.application.transition_command import DecideReviewRound, ReviewTransitionCommandService
from plm_assistant.modules.review.domain.round_progress import ReviewDecisionKind
from plm_assistant.modules.review.infrastructure.create_repository import SqlAlchemyReviewCreationRepository
from plm_assistant.modules.review.infrastructure.project_submission_repository import SqlAlchemyProjectReviewSubmissionRepository
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository
from plm_assistant.modules.review.infrastructure.transition_repository import SqlAlchemyReviewTransitionRepository
from plm_assistant.modules.trace.infrastructure.create_repository import SqlAlchemyTraceCreateRepository


ROOT = Path(__file__).resolve().parents[2]
physical = runpy.run_path(str(ROOT / "validation/prt-01-a11-a05-p01-physical-pg/verify.py"))
_run = physical["_run"]
PG_SOURCE, VECTOR_SOURCE = physical["PG_SOURCE"], physical["VECTOR_SOURCE"]
seed_user = runpy.run_path(str(
    ROOT / "validation/ai-02-a02-model-create/verify.py"
))["seed_user"]
PORT = 55434  # Required by the existing Requirement verifier.
ORIGIN = "http://localhost"
ITEMS = ("PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE")


class UnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"approved Prototype fixture used {name}")


def _measure_read_load(app, prefix: str, headers: dict[str, str], runtime,
                       *, sql_diagnostic: bool = False,
                       ) -> dict[str, float]:
    """Repeat twenty simultaneous ASGI GETs; not a network-service SLA."""
    query_durations: list[float] = []
    query_templates: dict[str, list[object]] = {}
    query_lock = threading.Lock()

    def before_query(conn, cursor, statement, parameters, context, executemany):
        context._prt_load_query_started = time.perf_counter()

    def after_query(conn, cursor, statement, parameters, context, executemany):
        elapsed = (time.perf_counter() - context._prt_load_query_started) * 1000
        fingerprint = hashlib.sha256(statement.encode("utf-8")).hexdigest()[:12]
        with query_lock:
            query_durations.append(elapsed)
            entry = query_templates.setdefault(
                fingerprint, [0, 0.0, 0.0, " ".join(statement.split())],
            )
            entry[0] += 1
            entry[1] += elapsed
            entry[2] = max(entry[2], elapsed)

    async def exercise() -> dict[str, float]:
        metrics = {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=ORIGIN, timeout=30.0,
        ) as client:
            health_samples = []
            for _ in range(3):
                ready = asyncio.Event()

                async def health_one() -> float:
                    await ready.wait()
                    started = time.perf_counter()
                    response = await client.get("/health/live")
                    elapsed = (time.perf_counter() - started) * 1000
                    assert response.status_code == 200, response.text
                    return elapsed

                tasks = [asyncio.create_task(health_one()) for _ in range(20)]
                ready.set()
                samples = sorted(await asyncio.gather(*tasks))
                health_samples.append(samples[18])
            print("PRT_A05_P04_CONTROL_HEALTH_LIVE "
                  f"median_round_p95_ms={statistics.median(health_samples):.2f}")
            for item in ITEMS:
                url = f"{prefix}/checklist-items/{item}/qualification"
                warm = await client.get(url, headers=headers)
                assert warm.status_code == 200, warm.text
                p95_rounds = []
                for round_no in range(1, 4):
                    ready = asyncio.Event()

                    async def one() -> float:
                        await ready.wait()
                        started = time.perf_counter()
                        response = await client.get(url, headers=headers)
                        elapsed = (time.perf_counter() - started) * 1000
                        assert response.status_code == 200, response.text
                        assert response.headers["etag"] == '"v10"'
                        assert response.json()["data"]["stage_key"] == "PROTOTYPE"
                        return elapsed

                    tasks = [asyncio.create_task(one()) for _ in range(20)]
                    ready.set()
                    samples = sorted(await asyncio.gather(*tasks))
                    p95 = samples[math.ceil(0.95 * len(samples)) - 1]
                    p95_rounds.append(p95)
                    print(f"PRT_A05_P04_READ_LOAD {item} round={round_no} "
                          f"concurrency=20 min_ms={samples[0]:.2f} "
                          f"p50_ms={statistics.median(samples):.2f} "
                          f"p95_ms={p95:.2f} max_ms={samples[-1]:.2f}")
                metrics[item] = statistics.median(p95_rounds)
                print(f"PRT_A05_P04_READ_LOAD_SUMMARY {item} "
                      f"median_round_p95_ms={metrics[item]:.2f}")
        return metrics

    if sql_diagnostic:
        event.listen(runtime._engine, "before_cursor_execute", before_query)
        event.listen(runtime._engine, "after_cursor_execute", after_query)
    try:
        result = asyncio.run(exercise())
        if not sql_diagnostic:
            return result
        samples = sorted(query_durations)
        assert samples
        print("PRT_A05_P04_SQL_DIAGNOSTIC "
              f"count={len(samples)} total_ms={sum(samples):.2f} "
              f"p95_statement_ms={samples[math.ceil(.95 * len(samples)) - 1]:.2f} "
              f"max_statement_ms={samples[-1]:.2f}")
        for fingerprint, entry in sorted(
            query_templates.items(), key=lambda item: item[1][1], reverse=True,
        )[:8]:
            print("PRT_A05_P04_SQL_TEMPLATE "
                  f"hash={fingerprint} count={entry[0]} "
                  f"total_ms={entry[1]:.2f} max_ms={entry[2]:.2f} "
                  f"statement={entry[3][:150]}")
        for fingerprint, entry in query_templates.items():
            if "prj_project_members.project_role" in entry[3]:
                print("PRT_A05_P04_AUTH_SQL "
                      f"hash={fingerprint} count={entry[0]} "
                      f"total_ms={entry[1]:.2f} max_ms={entry[2]:.2f} "
                      f"statement={entry[3]}")
        return result
    finally:
        if sql_diagnostic:
            event.remove(runtime._engine, "before_cursor_execute", before_query)
            event.remove(runtime._engine, "after_cursor_execute", after_query)


def _after_requirement(*, scratch: Path, runtime, database, ids, pm, pm_token,
                       reviewer, reviewer_token, requirement,
                       requirement_version, requirement_review_round,
                       workflow_id, guard, audit, sessions, origins, csrf,
                       project_evidence, additional_requirement,
                       mixed_not_required: bool = False,
                       conflicting_decision: bool = False,
                       coverage_mode: str | None = None,
                       isolation_checks: bool = False,
                       multi_prototype: bool = False,
                       read_load: bool = False,
                       read_load_sql_diagnostic: bool = False) -> None:
    project = ids["project"]
    second = additional_requirement if mixed_not_required else None
    if mixed_not_required:
        assert second is not None
    storage_root = scratch / "private-documents"
    storage_root.mkdir()
    storage = LocalFileStorage(storage_root)
    payload = b"Synthetic approved Prototype artifact; no customer data."
    digest = hashlib.sha256(payload).digest()
    file_id = uuid.uuid4()
    staging, locator = LocalFileStorage.locators(
        scope="PROJECT", project_id=project, file_object_id=file_id,
    )
    with storage.reserve_staging(staging) as stream:
        stream.write(payload)
    storage.publish_verified(
        staging, locator, expected_sha256=digest,
        expected_size=len(payload), max_bytes=100_000_000,
    )
    with psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                         dbname=database, autocommit=True) as db:
        template_id, template_version = uuid.uuid4(), uuid.uuid4()
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,"
                "name,current_template_version_ref,created_by) VALUES "
                "(%s,'PROJECT',%s,'Synthetic template',%s,%s)",
                (template_id, project, template_version, pm),
            )
            db.execute(
                "INSERT INTO plm.prt_template_versions("
                "prototype_template_version_id,prototype_template_id,scope,project_id,"
                "version_no,content_fingerprint,layout_contract,component_contract,"
                "applicable_terminals,declared_artifact_count,created_by) VALUES "
                "(%s,%s,'PROJECT',%s,1,%s,'{}','{}',ARRAY['DESKTOP_WEB'],0,%s)",
                (template_version, template_id, project, b"t" * 32, pm),
            )
        document_id = db.execute(
            "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
            "original_display_name,created_by) VALUES "
            "('PROJECT',%s,'PROJECT_RECORD','Prototype fixture','fixture.txt',%s) "
            "RETURNING document_id", (project, pm),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,"
            "storage_class,storage_locator,original_name_metadata,created_by,"
            "file_state,sha256,size_bytes,detected_mime,available_at) VALUES "
            "(%s,'PROJECT',%s,'PERSISTENT',%s,'fixture.txt',%s,'AVAILABLE',%s,%s,"
            "'text/plain',statement_timestamp())",
            (file_id, project, locator, pm, digest, len(payload)),
        )
        document_version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
            "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
            "source_metadata,created_by) VALUES "
            "(%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document_id, project, file_id, digest, len(payload), Jsonb({}), pm),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.doc_documents SET latest_version_ref=%s,"
            "effective_version_ref=%s WHERE document_id=%s",
            (document_version, document_version, document_id),
        )
        criteria = tuple(row[0] for row in db.execute(
            "SELECT acceptance_criterion_id FROM plm.req_acceptance_criteria "
            "WHERE requirement_version_id=%s ORDER BY ordinal",
            (requirement_version,),
        ).fetchall())
        assert len(criteria) == (2 if coverage_mode == "partial" or multi_prototype else 1)

    project_repository = SqlAlchemyProjectAuthorizationRepository()
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work, repository=project_repository,
    )
    receipts = SqlAlchemyIdempotencyReceipts()
    common = dict(unit_of_work=runtime.unit_of_work,
                  license_guard=guard, authorization=authorization,
                  receipts=receipts, audit=audit,
                  clock=lambda: datetime.now(timezone.utc))
    prototype = PrototypeIdentityCreateService(
        **common, access=SqlAlchemyProjectWriteAccess(),
        repository=SqlAlchemyPrototypeIdentityCreateRepository(),
    ).create_prototype(CreatePrototypeIdentity(
        pm_token, csrf, uuid.uuid4(), project,
        "Synthetic approved Prototype", str(uuid.uuid4()),
    ))
    templates = SqlAlchemyPrototypeVersionTemplateProof()
    requirements = SqlAlchemyPrototypeApprovedRequirementVersionProof()
    documents = SqlAlchemyPrototypeDocumentArtifactProof()
    current = PrototypeVersionCurrentValidator(
        templates=templates, requirements=requirements, documents=documents,
    )
    version = PrototypeVersionCreateService(
        **common, project_access=SqlAlchemyProjectWriteAccess(),
        requirements=requirements, templates=templates, documents=documents,
        repository=SqlAlchemyPrototypeVersionCreateRepository(),
    ).create(CreatePrototypeVersion(
        pm_token, csrf, uuid.uuid4(), project, prototype.prototype_id, 0,
        template_id, template_version,
        (VersionArtifactRef("DOCUMENT_VERSION", document_version),),
        (VersionRequirementRef(requirement.requirement_id, requirement_version),),
        {"interactions": []}, {"covered": 1}, str(uuid.uuid4()),
    ))
    reviewers = ProjectReviewerQualificationService(
        users=SqlAlchemyReviewUserAccess(), projects=project_repository,
    )
    subject = PrototypeReviewSubjectOwner(
        repository=SqlAlchemyPrototypeReviewSubjectRepository(),
        reviewers=reviewers, current=current, audit=audit,
        approval_trace=PrototypeApprovalTraceOwner(
            current=current, trace_links=SqlAlchemyTraceCreateRepository(),
            manifests=SqlAlchemyPrototypeApprovalTraceRepository(),
        ), clock=lambda: datetime.now(timezone.utc),
    )
    submission = PrototypeReviewSubmissionService(
        unit_of_work=runtime.unit_of_work, license_guard=guard,
        authorization=authorization, receipts=receipts,
        clock=lambda: datetime.now(timezone.utc),
        access=SqlAlchemyProjectWriteAccess(), reviewers=reviewers,
        replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
        reviews=ProjectReviewPersistenceService(
            creation_repository=SqlAlchemyReviewCreationRepository(),
            round_repository=SqlAlchemyReviewStartRepository(),
            audit=audit, subjects=subject,
            clock=lambda: datetime.now(timezone.utc),
        ), subjects=subject,
    ).submit(SubmitPrototypeVersionReview(
        pm_token, csrf, uuid.uuid4(), project, prototype.prototype_id,
        version.prototype_version_id, (reviewer,), "PROTOTYPE_ALL_V1",
        str(uuid.uuid4()),
    ))
    approved = ReviewTransitionCommandService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyReviewStartAccess(), projects=authorization,
        license_guard=guard, repository=SqlAlchemyReviewTransitionRepository(),
        receipts=receipts, audit=audit, subjects=subject,
        clock=lambda: datetime.now(timezone.utc),
    ).decide_idempotent(DecideReviewRound(
        reviewer_token, csrf, project, submission.review_id,
        submission.round_id, uuid.uuid4(), ReviewDecisionKind.APPROVE,
    ), idempotency_key=str(uuid.uuid4()))
    assert approved.state.value == "APPROVED"
    second_prototype = second_prototype_version = second_prototype_round = None
    if multi_prototype:
        second_prototype = PrototypeIdentityCreateService(
            **common, access=SqlAlchemyProjectWriteAccess(),
            repository=SqlAlchemyPrototypeIdentityCreateRepository(),
        ).create_prototype(CreatePrototypeIdentity(
            pm_token, csrf, uuid.uuid4(), project,
            "Second approved Prototype", str(uuid.uuid4()),
        ))
        second_prototype_version = PrototypeVersionCreateService(
            **common, project_access=SqlAlchemyProjectWriteAccess(),
            requirements=requirements, templates=templates, documents=documents,
            repository=SqlAlchemyPrototypeVersionCreateRepository(),
        ).create(CreatePrototypeVersion(
            pm_token, csrf, uuid.uuid4(), project,
            second_prototype.prototype_id, 0, template_id, template_version,
            (VersionArtifactRef("DOCUMENT_VERSION", document_version),),
            (VersionRequirementRef(requirement.requirement_id,
                                   requirement_version),),
            {"interactions": []}, {"covered": 1}, str(uuid.uuid4()),
        ))
        second_prototype_round = PrototypeReviewSubmissionService(
            unit_of_work=runtime.unit_of_work, license_guard=guard,
            authorization=authorization, receipts=receipts,
            clock=lambda: datetime.now(timezone.utc),
            access=SqlAlchemyProjectWriteAccess(), reviewers=reviewers,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=subject,
                clock=lambda: datetime.now(timezone.utc),
            ), subjects=subject,
        ).submit(SubmitPrototypeVersionReview(
            pm_token, csrf, uuid.uuid4(), project,
            second_prototype.prototype_id,
            second_prototype_version.prototype_version_id, (reviewer,),
            "PROTOTYPE_ALL_V1", str(uuid.uuid4()),
        ))
        second_approval = ReviewTransitionCommandService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyReviewStartAccess(), projects=authorization,
            license_guard=guard, repository=SqlAlchemyReviewTransitionRepository(),
            receipts=receipts, audit=audit, subjects=subject,
            clock=lambda: datetime.now(timezone.utc),
        ).decide_idempotent(DecideReviewRound(
            reviewer_token, csrf, project, second_prototype_round.review_id,
            second_prototype_round.round_id, uuid.uuid4(),
            ReviewDecisionKind.APPROVE,
        ), idempotency_key=str(uuid.uuid4()))
        assert second_approval.state.value == "APPROVED"
    prefix = f"/api/v1/projects/{project}/workflow"
    read_headers = {"cookie": "plm_session=" + pm_token.hex(), "host": "localhost"}
    unused = UnusedDependency()
    preview_only = create_app(
        workflow_checklist_qualification_router=(
            create_windows_workflow_checklist_qualification_router(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, documents=unused, downloads=unused,
                parse_results=unused, artifact_storage=storage,
            )
        ),
    )
    with TestClient(preview_only, base_url=ORIGIN) as client:
        incomplete_scope = client.get(
            f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
            headers=read_headers,
        )
        assert incomplete_scope.status_code == (409 if mixed_not_required else 200)
        missing_link = client.get(
            f"{prefix}/checklist-items/{ITEMS[1]}/qualification",
            headers=read_headers,
        )
        assert missing_link.status_code == 409, missing_link.text
    link_service = RequirementPrototypeLinkService(
        unit_of_work=runtime.unit_of_work,
        write_access=SqlAlchemyProjectWriteAccess(),
        read_access=SqlAlchemyProjectReadAccess(),
        license_guard=guard, authorization=authorization,
        repository=SqlAlchemyRequirementPrototypeLinkRepository(),
        version_reader=SqlAlchemyPrototypeVersionReadRepository(),
        current_validator=current, receipts=receipts, audit=audit,
    )
    if isolation_checks:
        with psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                             dbname=database, autocommit=True) as db:
            other_token = b"x" * 32
            other_pm = seed_user(
                db, "A05 Other Synthetic PM " + uuid.uuid4().hex[:8],
                "NONE", other_token,
            )
            other_code = "PRTX" + uuid.uuid4().hex[:12].upper()
            other = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES (%s,%s,'Other synthetic project',%s) "
                "RETURNING project_id",
                (other_code, other_code.lower(), other_pm),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES "
                "(%s,'PRTX','prtx','Other synthetic department') "
                "RETURNING department_id", (other,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,"
                "department_id,project_role) VALUES "
                "(%s,%s,%s,'PROJECT_MANAGER')", (other, other_pm, department),
            )
        try:
            link_service.create(CreateRequirementPrototypeLink(
                other_token, csrf, uuid.uuid4(), other,
                requirement.requirement_id, requirement_version,
                prototype.prototype_id, version.prototype_version_id,
                "VALIDATES", RequirementPrototypeCoverage(criteria, ()),
                str(uuid.uuid4()),
            ))
        except RequirementPrototypeLinkError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else:
            raise AssertionError("cross-project Link must not be created")
        with psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                             dbname=database, autocommit=True) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.prt_requirement_links WHERE project_id=%s",
                (other,),
            ).fetchone()[0] == 0
    initial_coverage = (RequirementPrototypeCoverage(
        (criteria[0],),
        (UncoveredAcceptanceCriterion(criteria[1], "Needs another check"),),
    ) if coverage_mode == "partial" or multi_prototype else
        RequirementPrototypeCoverage(criteria, ()))
    initial_purpose = "ILLUSTRATES" if coverage_mode == "illustrates" else "VALIDATES"
    link = link_service.create(CreateRequirementPrototypeLink(
        pm_token, csrf, uuid.uuid4(), project,
        requirement.requirement_id, requirement_version,
        prototype.prototype_id, version.prototype_version_id,
        initial_purpose, initial_coverage,
        str(uuid.uuid4()),
    ))
    assert link.link_state == "ACTIVE"
    if multi_prototype:
        overlap = link_service.create(CreateRequirementPrototypeLink(
            pm_token, csrf, uuid.uuid4(), project,
            requirement.requirement_id, requirement_version,
            second_prototype.prototype_id,
            second_prototype_version.prototype_version_id,
            "VALIDATES", initial_coverage, str(uuid.uuid4()),
        ))
        assert overlap.link_state == "ACTIVE"
        with TestClient(preview_only, base_url=ORIGIN) as client:
            scope = client.get(
                f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
                headers=read_headers,
            )
            assert scope.status_code == 200, scope.text
            missed = client.get(
                f"{prefix}/checklist-items/{ITEMS[1]}/qualification",
                headers=read_headers,
            )
            assert missed.status_code == 409, missed.text
        complement = link_service.supersede(SupersedeRequirementPrototypeLink(
            session_token=pm_token, csrf_token=csrf, trace_id=uuid.uuid4(),
            project_id=project,
            requirement_prototype_link_id=overlap.requirement_prototype_link_id,
            requirement_id=requirement.requirement_id,
            requirement_version_id=requirement_version,
            prototype_id=second_prototype.prototype_id,
            prototype_version_id=second_prototype_version.prototype_version_id,
            purpose="VALIDATES",
            coverage=RequirementPrototypeCoverage(
                (criteria[1],),
                (UncoveredAcceptanceCriterion(criteria[0],
                                               "Covered by first Prototype"),),
            ),
            expected_version=0, idempotency_key=str(uuid.uuid4()),
        ))
        assert complement.link_state == "ACTIVE"

    if second is not None:
        with TestClient(preview_only, base_url=ORIGIN) as client:
            for item in ITEMS:
                missing_decision = client.get(
                    f"{prefix}/checklist-items/{item}/qualification",
                    headers=read_headers,
                )
                assert missing_decision.status_code == 409, missing_decision.text
        second_root, second_version, second_round = second
        not_required = PrototypeIdentityCreateService(
            **common, access=SqlAlchemyProjectWriteAccess(),
            repository=SqlAlchemyPrototypeIdentityCreateRepository(),
        ).create_prototype(CreatePrototypeIdentity(
            pm_token, csrf, uuid.uuid4(), project,
            "Synthetic no-prototype scope", str(uuid.uuid4()),
        ))
        decision_refs = ((second_version,) if not conflicting_decision else
                         tuple(sorted((second_version, requirement_version),
                                      key=lambda value: value.int)))
        decision = PrototypeScopeDecisionService(
            **common, access=SqlAlchemyProjectWriteAccess(),
            repository=SqlAlchemyPrototypeScopeDecisionRepository(),
        ).mark_not_required(MarkPrototypeNotRequired(
            pm_token, csrf, uuid.uuid4(), project,
            not_required.prototype_id, 0, decision_refs,
            "Second synthetic requirement needs no interactive prototype",
            "Use standard configuration", None, None, str(uuid.uuid4()),
        ))
        assert decision.prototype_state == "NOT_REQUIRED"
        assert decision.confirmed_by == pm
        if conflicting_decision:
            with TestClient(preview_only, base_url=ORIGIN) as client:
                for item in ITEMS:
                    conflict = client.get(
                        f"{prefix}/checklist-items/{item}/qualification",
                        headers=read_headers,
                    )
                    assert conflict.status_code == 409, conflict.text
            with psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                                 dbname=database, autocommit=True) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records "
                    "WHERE project_id=%s AND stage_key='PROTOTYPE'",
                    (project,),
                ).fetchone()[0] == 0
            return

    if coverage_mode in {"partial", "illustrates"}:
        with TestClient(preview_only, base_url=ORIGIN) as client:
            scope = client.get(
                f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
                headers=read_headers,
            )
            assert scope.status_code == 200, scope.text
            incomplete_coverage = client.get(
                f"{prefix}/checklist-items/{ITEMS[1]}/qualification",
                headers=read_headers,
            )
            assert incomplete_coverage.status_code == 409, incomplete_coverage.text
        if coverage_mode == "partial":
            replacement = link_service.supersede(SupersedeRequirementPrototypeLink(
                session_token=pm_token, csrf_token=csrf,
                trace_id=uuid.uuid4(), project_id=project,
                requirement_prototype_link_id=link.requirement_prototype_link_id,
                requirement_id=requirement.requirement_id,
                requirement_version_id=requirement_version,
                prototype_id=prototype.prototype_id,
                prototype_version_id=version.prototype_version_id,
                purpose="VALIDATES",
                coverage=RequirementPrototypeCoverage(criteria, ()),
                expected_version=0, idempotency_key=str(uuid.uuid4()),
            ))
            assert replacement.link_state == "ACTIVE"
        else:
            additional = link_service.create(CreateRequirementPrototypeLink(
                pm_token, csrf, uuid.uuid4(), project,
                requirement.requirement_id, requirement_version,
                prototype.prototype_id, version.prototype_version_id,
                "VALIDATES", RequirementPrototypeCoverage(criteria, ()),
                str(uuid.uuid4()),
            ))
            assert additional.link_state == "ACTIVE"

    def build_app(db_runtime, route_sessions=sessions):
        return create_app(
            workflow_checklist_qualification_router=(
                create_windows_workflow_checklist_qualification_router(
                    db_runtime, sessions=route_sessions, origins=origins,
                    license_guard=guard, documents=unused, downloads=unused,
                    parse_results=unused, artifact_storage=storage,
                )
            ),
            workflow_checklist_record_router=(
                create_windows_workflow_checklist_record_router(
                    db_runtime, sessions=route_sessions, origins=origins,
                    license_guard=guard, audit=audit, documents=unused,
                    downloads=unused, parse_results=unused,
                    artifact_storage=storage,
                )
            ),
            workflow_transition_router=(
                create_windows_workflow_stage_transition_router(
                    db_runtime, sessions=route_sessions, origins=origins,
                    license_guard=guard, audit=audit, documents=unused,
                    downloads=unused, parse_results=unused,
                    artifact_storage=storage,
                )
            ),
        )
    app = build_app(runtime)
    write_headers = {**read_headers, "x-csrf-token": csrf.hex(), "origin": ORIGIN}
    if read_load:
        preview_auth = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        with runtime.unit_of_work() as holding_tx:
            proof = preview_auth.require_in_transaction(
                holding_tx, user_id=pm, project_id=project,
                operation="WORKFLOW_CHECKLIST_PREVIEW",
            )
            assert proof.project_role == "PROJECT_MANAGER"
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                parallel_reader = pool.submit(
                    preview_auth.require, user_id=pm, project_id=project,
                    operation="WORKFLOW_CHECKLIST_PREVIEW",
                )
                assert parallel_reader.result(timeout=5).project_role == "PROJECT_MANAGER"
            try:
                with psycopg.connect(
                    host="127.0.0.1", port=PORT, user="poc_admin",
                    dbname=database, autocommit=True,
                ) as db, db.transaction():
                    db.execute("SET LOCAL lock_timeout='200ms'")
                    db.execute(
                        "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                        "WHERE project_id=%s AND user_id=%s AND state='ACTIVE'",
                        (project, pm),
                    )
            except psycopg.errors.LockNotAvailable:
                pass
            else:
                raise AssertionError("preview shared lock failed to fence revocation")
        print("PRT_A05_P04_SHARED_LOCK_PROOF: two readers coexist; "
              "concurrent member revocation waits")
        p95 = _measure_read_load(
            app, prefix, read_headers, runtime,
            sql_diagnostic=read_load_sql_diagnostic,
        )
        assert set(p95) == set(ITEMS)
        expanded_runtime = create_database_runtime(
            runtime._engine.url,
            options=DatabaseEngineOptions(pool_size=20, max_overflow=0),
        )
        try:
            expanded_sessions = SessionService(
                unit_of_work=expanded_runtime.unit_of_work,
                repository=SqlAlchemySessionRepository(),
                issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
                audit=audit, idempotency=SqlAlchemyIdempotencyReceipts(),
            )
            expanded_p95 = _measure_read_load(
                build_app(expanded_runtime, expanded_sessions),
                prefix, read_headers, expanded_runtime,
                sql_diagnostic=read_load_sql_diagnostic,
            )
            print("PRT_A05_P04_POOL_DIAGNOSTIC "
                  f"default={p95} pool20={expanded_p95}")
        finally:
            expanded_runtime.dispose()
    with TestClient(app, base_url=ORIGIN) as client:
        if isolation_checks:
            with psycopg.connect(host="127.0.0.1", port=PORT,
                                 user="poc_admin", dbname=database,
                                 autocommit=True) as db:
                db.execute(
                    "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                    "WHERE project_id=%s AND user_id=%s AND state='ACTIVE'",
                    (project, pm),
                )
            denied_read = client.get(
                f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
                headers=read_headers,
            )
            assert denied_read.status_code == 404, denied_read.text
            assert denied_read.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
            denied_write = client.post(
                f"{prefix}/checklist-items/{ITEMS[0]}:record",
                json={"result": "PASS", "reason": "Revoked member",
                      "impact": "Validation only",
                      "evidence_refs": [str(project_evidence)],
                      "exception_refs": []},
                headers={**write_headers, "if-match": '"v10"',
                         "idempotency-key": str(uuid.uuid4())},
            )
            assert denied_write.status_code == 404, denied_write.text
            assert denied_write.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
            with psycopg.connect(host="127.0.0.1", port=PORT,
                                 user="poc_admin", dbname=database,
                                 autocommit=True) as db:
                db.execute(
                    "UPDATE plm.prj_project_members SET state='ACTIVE' "
                    "WHERE project_id=%s AND user_id=%s AND state='SUSPENDED'",
                    (project, pm),
                )
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records "
                    "WHERE project_id=%s AND stage_key='PROTOTYPE'",
                    (project,),
                ).fetchone()[0] == 0
        artifact_path = storage_root / locator
        artifact_path.write_bytes(payload[:-1] + b"!")
        for item in ITEMS:
            damaged = client.get(
                f"{prefix}/checklist-items/{item}/qualification",
                headers=read_headers,
            )
            assert damaged.status_code == 409, damaged.text
        artifact_path.write_bytes(payload)
        expected_subjects = [
            {"subject_type": "PRT-03", "subject_id": str(prototype.prototype_id),
             "subject_version_id": str(version.prototype_version_id),
             "review_round_ref": str(submission.round_id)},
            {"subject_type": "REQ-03", "subject_id": str(requirement.requirement_id),
             "subject_version_id": str(requirement_version),
             "review_round_ref": str(requirement_review_round)},
        ]
        if multi_prototype:
            expected_subjects.append({
                "subject_type": "PRT-03",
                "subject_id": str(second_prototype.prototype_id),
                "subject_version_id": str(second_prototype_version.prototype_version_id),
                "review_round_ref": str(second_prototype_round.round_id),
            })
        if second is not None:
            expected_subjects.append({
                "subject_type": "REQ-03", "subject_id": str(second_root.requirement_id),
                "subject_version_id": str(second_version),
                "review_round_ref": str(second_round),
            })
        expected_subjects.sort(key=lambda value: (
            value["subject_type"], uuid.UUID(value["subject_id"]).int,
            uuid.UUID(value["subject_version_id"]).int,
        ))
        etag = '"v10"'
        for item in ITEMS:
            preview = client.get(
                f"{prefix}/checklist-items/{item}/qualification",
                headers=read_headers,
            )
            assert preview.status_code == 200, preview.text
            assert preview.headers["etag"] == etag
            assert preview.json()["data"]["qualified_subjects"] == expected_subjects
            evidence = preview.json()["data"]["evidence_refs"]
            assert evidence == [str(project_evidence)]
            if item == ITEMS[0]:
                artifact_path.write_bytes(payload[:-1] + b"!")
                stale_write = client.post(
                    f"{prefix}/checklist-items/{item}:record",
                    json={"result": "PASS", "reason": "Stale preview",
                          "impact": "Validation only", "evidence_refs": evidence,
                          "exception_refs": []},
                    headers={**write_headers, "if-match": etag,
                             "idempotency-key": str(uuid.uuid4())},
                )
                assert stale_write.status_code == 409, stale_write.text
                artifact_path.write_bytes(payload)
            result = client.post(
                f"{prefix}/checklist-items/{item}:record",
                json={"result": "PASS", "reason": "Approved synthetic scope",
                      "impact": "Validation only", "evidence_refs": evidence,
                      "exception_refs": []},
                headers={**write_headers, "if-match": etag,
                         "idempotency-key": str(uuid.uuid4())},
            )
            assert result.status_code == 200, result.text
            etag = result.headers["etag"]
        assert etag == '"v12"'
        transition = client.post(
            f"{prefix}:transition",
            json={"target_stage_key": "SOLUTION",
                  "reason": "Approved synthetic Prototype complete",
                  "gate_snapshot_refs": []},
            headers={**write_headers, "if-match": etag,
                     "idempotency-key": str(uuid.uuid4())},
        )
        assert transition.status_code == 200, transition.text
        assert transition.json()["data"]["to_stage"] == "SOLUTION"
        assert transition.headers["etag"] == '"v13"'
    with psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                         dbname=database, autocommit=True) as db:
        assert db.execute(
            "SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows "
            "WHERE workflow_id=%s", (workflow_id,),
        ).fetchone() == ("SOLUTION", 13)


def main(*, mixed_not_required: bool = False,
         conflicting_decision: bool = False,
         coverage_mode: str | None = None,
         isolation_checks: bool = False,
         multi_prototype: bool = False,
         read_load: bool = False,
         read_load_sql_diagnostic: bool = False) -> None:
    if conflicting_decision and not mixed_not_required:
        raise ValueError("conflict mode requires mixed scope")
    if coverage_mode not in {None, "partial", "illustrates"}:
        raise ValueError("unknown coverage mode")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError("port 55434 is occupied; existing PostgreSQL untouched")
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    scratch = Path(tempfile.mkdtemp(prefix="plm-prt-a05-p03-", dir=temp_root)).resolve()
    if not scratch.is_relative_to(temp_root) or not str(scratch).isascii():
        raise RuntimeError("isolated ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    try:
        for name in ("bin", "lib", "share"):
            shutil.copytree(PG_SOURCE / name, install / name)
        shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
        shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
        for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
            shutil.copy2(path, install / "share/extension" / path.name)
        binaries = install / "bin"
        data, log = scratch / "data", scratch / "postgres.log"
        _run([str(binaries / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
              "-A", "trust", "--no-locale", "-E", "UTF8"])
        _run([str(binaries / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
              "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start"], detached=True)
        req = runpy.run_path(str(ROOT / "validation/req-01-a12-a05-workflow-pg/verify.py"))
        req["main"](
            include_second=mixed_not_required,
            include_extra_criterion=(coverage_mode == "partial" or multi_prototype),
            after_prototype=lambda **context: _after_requirement(
                scratch=scratch, mixed_not_required=mixed_not_required,
                conflicting_decision=conflicting_decision,
                coverage_mode=coverage_mode,
                isolation_checks=isolation_checks,
                multi_prototype=multi_prototype,
                read_load=read_load,
                read_load_sql_diagnostic=read_load_sql_diagnostic,
                **context,
            ),
        )
        if read_load:
            print("PRT_01_A11_A05_P04_P01_READ_LOAD_MEASURED: "
                  "twenty concurrent GETs per Prototype item, real PG and file")
        elif multi_prototype:
            print("PRT_01_A11_A05_P03_A03_MULTI_PROTOTYPE_HTTP_PG_PASS: "
                  "overlapping Links left one criterion uncovered and failed; "
                  "formal complementary Link union passed")
        elif isolation_checks:
            print("PRT_01_A11_A05_P03_A03_ISOLATION_HTTP_PG_PASS: "
                  "cross-project Link rejected; suspended PM read/write "
                  "denied without Checklist history; restored scope advances")
        elif coverage_mode is not None:
            print("PRT_01_A11_A05_P03_A03_" + coverage_mode.upper()
                  + "_COVERAGE_HTTP_PG_PASS: incomplete coverage rejected; "
                  "corrected via formal Link service; two PASS and SOLUTION")
        elif conflicting_decision:
            print("PRT_01_A11_A05_P03_A02_CONFLICT_HTTP_PG_PASS: same "
                  "Requirement claimed by Approved Prototype and NOT_REQUIRED "
                  "was rejected without Prototype checklist history")
        elif mixed_not_required:
            print("PRT_01_A11_A05_P03_A02_MIXED_HTTP_PG_PASS: two approved "
                  "Requirements partitioned between Approved Prototype and "
                  "NOT_REQUIRED, missing decision/damaged bytes rejected, "
                  "two PASS and SOLUTION transition")
        else:
            print("PRT_01_A11_A05_P03_A01_APPROVED_HTTP_PG_PASS: approved "
                  "Prototype, missing Link/damaged bytes rejected, complete Link, "
                  "two PASS and SOLUTION transition")
    finally:
        control, data = install / "bin/pg_ctl.exe", scratch / "data"
        if control.is_file() and data.is_dir():
            status = subprocess.run(
                [str(control), "-D", str(data), "status"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
            if status.returncode == 0:
                _run([str(control), "-D", str(data), "-m", "fast", "-w", "stop"])
                status = subprocess.run(
                    [str(control), "-D", str(data), "status"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=30, check=False,
                )
            if status.returncode == 0:
                raise RuntimeError("isolated PostgreSQL still running; data preserved")
        if (scratch.is_relative_to(temp_root) and scratch != temp_root
                and scratch.name.startswith("plm-prt-a05-p03-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
