"""Isolated PG/HTTP proof of a genuinely approved Prototype scope."""

from __future__ import annotations

import hashlib
import runpy
import shutil
import socket
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_workflow_checklist import (
    create_windows_workflow_checklist_qualification_router,
    create_windows_workflow_checklist_record_router,
    create_windows_workflow_stage_transition_router,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import SqlAlchemyPrototypeDocumentArtifactProof
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
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
from plm_assistant.modules.prototype.application.requirement_links import (
    CreateRequirementPrototypeLink, RequirementPrototypeCoverage,
    RequirementPrototypeLinkService,
)
from plm_assistant.modules.prototype.application.review_subject import PrototypeReviewSubjectOwner
from plm_assistant.modules.prototype.application.submit_review import (
    PrototypeReviewSubmissionService, SubmitPrototypeVersionReview,
)
from plm_assistant.modules.prototype.infrastructure.approval_trace_repository import SqlAlchemyPrototypeApprovalTraceRepository
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import SqlAlchemyPrototypeIdentityCreateRepository
from plm_assistant.modules.prototype.infrastructure.requirement_link_repository import SqlAlchemyRequirementPrototypeLinkRepository
from plm_assistant.modules.prototype.infrastructure.review_subject_repository import SqlAlchemyPrototypeReviewSubjectRepository
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
PORT = 55434  # Required by the existing Requirement verifier.
ORIGIN = "http://localhost"
ITEMS = ("PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE")


class UnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"approved Prototype fixture used {name}")


def _after_requirement(*, scratch: Path, runtime, database, ids, pm, pm_token,
                       reviewer, reviewer_token, requirement,
                       requirement_version, requirement_review_round,
                       workflow_id, guard, audit, sessions, origins, csrf,
                       project_evidence) -> None:
    project = ids["project"]
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
        criterion = db.execute(
            "SELECT acceptance_criterion_id FROM plm.req_acceptance_criteria "
            "WHERE requirement_version_id=%s", (requirement_version,),
        ).fetchone()[0]

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
        assert client.get(
            f"{prefix}/checklist-items/{ITEMS[0]}/qualification",
            headers=read_headers,
        ).status_code == 200
        missing_link = client.get(
            f"{prefix}/checklist-items/{ITEMS[1]}/qualification",
            headers=read_headers,
        )
        assert missing_link.status_code == 409, missing_link.text
    link = RequirementPrototypeLinkService(
        unit_of_work=runtime.unit_of_work,
        write_access=SqlAlchemyProjectWriteAccess(),
        read_access=SqlAlchemyProjectReadAccess(),
        license_guard=guard, authorization=authorization,
        repository=SqlAlchemyRequirementPrototypeLinkRepository(),
        version_reader=SqlAlchemyPrototypeVersionReadRepository(),
        current_validator=current, receipts=receipts, audit=audit,
    ).create(CreateRequirementPrototypeLink(
        pm_token, csrf, uuid.uuid4(), project,
        requirement.requirement_id, requirement_version,
        prototype.prototype_id, version.prototype_version_id,
        "VALIDATES", RequirementPrototypeCoverage((criterion,), ()),
        str(uuid.uuid4()),
    ))
    assert link.link_state == "ACTIVE"

    app = create_app(
        workflow_checklist_qualification_router=(
            create_windows_workflow_checklist_qualification_router(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, documents=unused, downloads=unused,
                parse_results=unused, artifact_storage=storage,
            )
        ),
        workflow_checklist_record_router=(
            create_windows_workflow_checklist_record_router(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit, documents=unused,
                downloads=unused, parse_results=unused,
                artifact_storage=storage,
            )
        ),
        workflow_transition_router=(
            create_windows_workflow_stage_transition_router(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit, documents=unused,
                downloads=unused, parse_results=unused,
                artifact_storage=storage,
            )
        ),
    )
    write_headers = {**read_headers, "x-csrf-token": csrf.hex(), "origin": ORIGIN}
    with TestClient(app, base_url=ORIGIN) as client:
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


def main() -> None:
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
        req["main"](after_prototype=lambda **context: _after_requirement(
            scratch=scratch, **context,
        ))
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
