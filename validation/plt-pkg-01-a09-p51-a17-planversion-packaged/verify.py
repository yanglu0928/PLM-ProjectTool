"""Packaged PlanVersion Edge/HTTPS/PG proof, layered on the P51-A05 runner."""

from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

a05 = runpy.run_path(str(ROOT / "validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py"))
plan_edge = runpy.run_path(str(ROOT / "validation/plan-version-edge-postgres/verify.py"))
section_submit = runpy.run_path(str(
    ROOT / "validation/sol-05-a04-p13-p05-p03-section-review-submit-windows/verify.py"))


def _approved_section_fixture(context: dict, *, project: uuid.UUID,
                              actor: uuid.UUID, requirement: uuid.UUID,
                              requirement_version: uuid.UUID,
                              document_version: uuid.UUID,
                              evidence: uuid.UUID) -> tuple[bytes, bytes]:
    """Create a synthetic Approved Section through real SOL/Review Owners."""
    import hashlib

    from fastapi.testclient import TestClient
    import httpx
    from plm_assistant.entrypoints.api import create_app
    from plm_assistant.entrypoints.windows_project_review import (
        create_windows_project_review_router,
    )
    from plm_assistant.entrypoints.windows_solution_outline import (
        create_windows_section_review_submission_router,
        create_windows_section_version_validate_router,
    )
    from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
    from plm_assistant.modules.auth.application.session_service import SessionService
    from plm_assistant.modules.auth.infrastructure.project_read_access import (
        SqlAlchemyProjectReadAccess,
    )
    from plm_assistant.modules.auth.infrastructure.project_write_access import (
        SqlAlchemyProjectWriteAccess,
    )
    from plm_assistant.modules.auth.infrastructure.session_repository import (
        SqlAlchemySessionRepository,
    )
    from plm_assistant.modules.document.application.prove_fixed_source import (
        DocumentFixedSourceProofService,
    )
    from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
        SqlAlchemyParseResultReadRepository,
    )
    from plm_assistant.modules.document.infrastructure.reference_version_identity import (
        SqlAlchemyReferenceVersionIdentity,
    )
    from plm_assistant.modules.evidence.application.fixed_project_source import (
        EvidenceFixedProjectSourceService,
    )
    from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
        SqlAlchemyEvidenceFixedSourceRepository,
    )
    from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
        SqlAlchemyIdempotencyReceipts,
    )
    from plm_assistant.modules.project.application.authorization import (
        ProjectAuthorizationService,
    )
    from plm_assistant.modules.project.infrastructure.authorization_repository import (
        SqlAlchemyProjectAuthorizationRepository,
    )
    from plm_assistant.modules.requirement.application.outline_version_proof import (
        OutlineRequirementUseProofService,
    )
    from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
        SqlAlchemyPrototypeApprovedRequirementVersionProof,
    )
    from plm_assistant.modules.solution.application.create_outline import (
        CreateOutline, OutlineCreateService,
    )
    from plm_assistant.modules.solution.application.create_section import (
        CreateSection, SectionCreateService,
    )
    from plm_assistant.modules.solution.application.create_section_version import (
        CreateSectionVersion, SectionVersionCreateService,
    )
    from plm_assistant.modules.solution.application.prove_section_version_input import (
        SectionVersionInputProofService,
    )
    from plm_assistant.modules.solution.application.section_version_input import (
        SectionRequirementRef, SectionVersionDraftInput,
    )
    from plm_assistant.modules.solution.infrastructure.outline_create_repository import (
        SqlAlchemyOutlineCreateRepository,
    )
    from plm_assistant.modules.solution.infrastructure.section_create_repository import (
        SqlAlchemySectionCreateRepository,
    )
    from plm_assistant.modules.solution.infrastructure.section_document_content_proof import (
        SectionDocumentContentProofAdapter,
    )
    from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import (
        SectionEvidenceUseProofAdapter,
    )
    from plm_assistant.modules.solution.infrastructure.section_version_base import (
        SqlAlchemyCurrentSectionVersionBase,
    )
    from plm_assistant.modules.solution.infrastructure.section_version_create_repository import (
        SqlAlchemySectionVersionCreateRepository,
    )
    from plm_assistant.modules.trace.application.create_link import (
        CreateTraceLinkRefs,
    )
    from plm_assistant.modules.trace.application.target_proof import (
        TraceResourceVersionRef,
    )

    fixture_db = context["fixture_db"]
    runtime, audit, guard = context["runtime"], context["audit"], context["license_guard"]
    origin = context["origin"]
    # The upstream Handover review harness deliberately leaves its shared
    # browser client signed in as an unrelated observer. Acquire a matched
    # manager Session/CSRF pair through the packaged Login HTTP boundary.
    with fixture_db() as db:
        db.execute("DELETE FROM plm.auth_login_rate_buckets")
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as manager_client:
        manager_login = manager_client.post(
            "/api/v1/auth/login", headers={"origin": origin}, json={
                "username": "Synthetic Packaged User",
                "password": "synthetic-packaged-login-password",
            },
        )
        if manager_login.status_code != 200:
            raise AssertionError(
                f"packaged synthetic manager login rejected: {manager_login.status_code}"
            )
        login_data = manager_login.json()["data"]
        if uuid.UUID(login_data["user"]["user_id"]) != actor:
            raise AssertionError("packaged synthetic manager identity mismatch")
        token = bytes.fromhex(manager_client.cookies["plm_session"])
        csrf = bytes.fromhex(login_data["csrf_token"])
    if len(token) != 32 or len(csrf) != 32:
        raise AssertionError("packaged synthetic manager Session proof malformed")
    authorization_repo = SqlAlchemyProjectAuthorizationRepository()
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work, repository=authorization_repo)
    receipts = SqlAlchemyIdempotencyReceipts()
    common = dict(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=guard, authorization=authorization, receipts=receipts, audit=audit,
    )
    outline = OutlineCreateService(
        **common, repository=SqlAlchemyOutlineCreateRepository()).create(
            CreateOutline(token, csrf, uuid.uuid4(), project,
                          "A17 Synthetic Approved Source", "a17-outline-create-0001"))
    section = SectionCreateService(
        **common, repository=SqlAlchemySectionCreateRepository()).create(
            CreateSection(token, csrf, uuid.uuid4(), project,
                          outline.solution_outline_id, "a17-source",
                          "a17-section-create-0001"))

    fixed = DocumentFixedSourceProofService(
        documents=context["documents"], downloads=context["downloads"],
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=context["parse_results"],
    )
    evidence_sources = EvidenceFixedProjectSourceService(
        sessions=SqlAlchemyProjectReadAccess(), projects=authorization_repo,
        evidence=SqlAlchemyEvidenceFixedSourceRepository(), documents=fixed,
        allowed_project_roles=frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
    )
    inputs = SectionVersionInputProofService(
        bases=SqlAlchemyCurrentSectionVersionBase(),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
    )
    version_owner = SectionVersionCreateService(
        **common, inputs=inputs, repository=SqlAlchemySectionVersionCreateRepository())

    with fixture_db() as db:
        source = db.execute(
            "SELECT f.storage_locator,f.sha256,f.size_bytes FROM plm.doc_document_versions v "
            "JOIN plm.doc_file_objects f ON f.file_object_id=v.file_object_id "
            "WHERE v.document_version_id=%s AND v.project_id=%s",
            (document_version, project),
        ).fetchone()
    assert source is not None, "synthetic fixed Document source missing"
    locator = source[0]
    content = b"Synthetic Prototype fixed document; not customer information.\n"
    if hashlib.sha256(content).digest() != source[1] or len(content) != source[2]:
        raise AssertionError("synthetic fixed Document bytes differ from metadata")
    source_path = Path(fixture_db.data_root) / locator
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)
    draft = SectionVersionDraftInput(
        project, section.solution_section_id, "A17 synthetic implementation section",
        document_version, None,
        (SectionRequirementRef(requirement, requirement_version),),
        (evidence,), ({"basis": "synthetic package fixture only"},), (),
        "NONE_REQUIRED", "No specialist design is required for this fixture", (),
    )
    version = version_owner.create(CreateSectionVersion(
        token, csrf, uuid.uuid4(), draft, "a17-section-version-0001"))
    creator, _ = section_submit["_trace_services"](
        runtime=runtime, license_guard=guard, audit=audit)
    creator.create_refs(CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project,
        TraceResourceVersionRef("REQ-03", requirement, requirement_version),
        TraceResourceVersionRef("SOL-05", section.solution_section_id,
                                version.solution_section_version_id),
        "IMPLEMENTS"), idempotency_key="a17-section-trace-0001")

    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy([origin])
    validation_router = create_windows_section_version_validate_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit, documents=context["documents"],
        downloads=context["downloads"], parse_results=context["parse_results"])
    path = (f"/api/v1/projects/{project}/solution-sections/"
            f"{section.solution_section_id}/versions/"
            f"{version.solution_section_version_id}")
    headers = {"cookie": "plm_session=" + token.hex(), "origin": origin,
               "x-csrf-token": csrf.hex(), "idempotency-key": "a17-section-validate-0001"}
    with TestClient(create_app(solution_section_version_validate_router=validation_router),
                    base_url=origin) as app:
        result = app.post(path + ":validate", headers=headers)
        assert result.status_code == 200, result.text
        assert result.json()["data"]["ready_for_review"] is True, result.text
        assert set(result.json()["data"]["facts"].values()) == {"PASS"}, result.text

    import hashlib
    import secrets

    reviewer_token, reviewer_csrf = secrets.token_bytes(32), secrets.token_bytes(32)
    with fixture_db() as db:
        reviewer = db.execute(
            "SELECT u.user_id,u.credential_version FROM plm.auth_users u "
            "JOIN plm.prj_project_members m ON m.user_id=u.user_id "
            "WHERE m.project_id=%s AND u.username_normalized='synthetic handover customer' "
            "AND m.state='ACTIVE'", (project,),
        ).fetchone()
    assert reviewer is not None, "synthetic assigned reviewer session missing"
    with fixture_db() as db:
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) VALUES "
            "(%s,%s,%s,%s,statement_timestamp()+interval '30 minutes',"
            "statement_timestamp()+interval '2 hours')",
            (hashlib.sha256(reviewer_token).digest(), hashlib.sha256(reviewer_csrf).digest(),
             reviewer[0], reviewer[1]),
        )
    submission_router = create_windows_section_review_submission_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit, documents=context["documents"],
        downloads=context["downloads"], parse_results=context["parse_results"])
    submission_path = (f"/api/v1/projects/{project}/solution-sections/"
                       f"{section.solution_section_id}/versions/"
                       f"{version.solution_section_version_id}:submit-review")
    with TestClient(create_app(solution_section_review_submission_router=submission_router),
                    base_url=origin) as app:
        submitted = app.post(submission_path, headers=headers | {
            "idempotency-key": "a17-section-submit-0001"}, json={
                "reviewer_ids": [str(reviewer[0])],
                "policy_ref": "SOLUTION_SECTION_ALL_V1",
                "due_at": None, "submission_note": None,
            })
        assert submitted.status_code == 201, submitted.text
        review_id = uuid.UUID(submitted.json()["data"]["review_id"])
        round_id = uuid.UUID(submitted.json()["data"]["review_round_id"])
    review_router = create_windows_project_review_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=guard, audit=audit, documents=context["documents"],
        downloads=context["downloads"], parse_results=context["parse_results"])
    decision_path = (f"/api/v1/projects/{project}/reviews/{review_id}/rounds/"
                     f"{round_id}:decide")
    review_headers = {"cookie": "plm_session=" + reviewer_token.hex(), "origin": origin,
                      "x-csrf-token": reviewer_csrf.hex(),
                      "idempotency-key": "a17-section-approve-0001"}
    with TestClient(create_app(review_command_router=review_router),
                    base_url=origin) as app:
        decided = app.post(decision_path, headers=review_headers,
                           json={"decision": "APPROVE", "comment": None})
        assert decided.status_code == 200, decided.text
    with fixture_db() as db:
        approved = db.execute(
            "SELECT v.version_state,s.current_approved_version_ref,r.review_state,rr.round_state "
            "FROM plm.sol_section_versions v JOIN plm.sol_sections s "
            "ON s.solution_section_id=v.solution_section_id "
            "JOIN plm.rvw_reviews r ON r.review_id=v.review_ref "
            "JOIN plm.rvw_review_rounds rr ON rr.review_round_id=v.review_round_ref "
            "WHERE v.solution_section_version_id=%s", (version.solution_section_version_id,),
        ).fetchone()
    assert approved == ("APPROVED", version.solution_section_version_id,
                        "APPROVED", "APPROVED"), approved
    # The following inherited Requirement Review probe requires a CUSTOMER_MEMBER.
    # Prepare that role only after this synthetic Section Review has completed.
    with fixture_db() as db, db.transaction():
        db.execute(
            "UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' "
            "WHERE project_id=%s AND user_id=%s AND state='ACTIVE'",
            (project, reviewer[0]),
        )
        member = db.execute(
            "SELECT project_role,state FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id=%s", (project, reviewer[0]),
        ).fetchone()
    assert member == ("CUSTOMER_MEMBER", "ACTIVE"), member
    print("P51_A17_SYNTHETIC_SECTION_OWNER_REVIEW_PASS", flush=True)
    return token, csrf


def skip_unrelated_survey_followups(_state, **_context) -> None:
    # P51-A17 is the PlanVersion slice. The enclosing P51-A05 chain has already
    # exercised Survey creation/review; its post-approval and synthetic-expiry
    # Edge reruns are unrelated and can fail on Chromium profile cleanup after
    # the PlanVersion callback has completed.
    return None


a05["p51"]["after_approval"] = skip_unrelated_survey_followups
a05["p51"]["after_expiry"] = skip_unrelated_survey_followups
_handover_review = a05["p51"]["browser_probe"].__globals__["handover_review"]
_original_handover_browser_probe = _handover_review["browser_probe"]
_handover_globals = _original_handover_browser_probe.__globals__
_handover_globals["_a17_original_handover_browser_probe"] = _original_handover_browser_probe


def reset_disposable_login_rate_buckets(**context) -> None:
    # At this boundary only the least-privileged connection is forwarded.
    # It owns its disposable login throttle rows, so clear them before Edge
    # probes while preserving the historical callback globals expected by A05.
    with context["connect_db"]() as db:
        db.execute("DELETE FROM plm.auth_login_rate_buckets")
    _a17_original_handover_browser_probe(**context)


import types

_handover_review["browser_probe"] = types.FunctionType(
    reset_disposable_login_rate_buckets.__code__, _handover_globals,
    reset_disposable_login_rate_buckets.__name__,
    reset_disposable_login_rate_buckets.__defaults__,
)



def _plugin_package_import_pg_smoke(context: dict, *, actor_id: uuid.UUID) -> None:
    """Verify the A08 service against the same disposable PostgreSQL 18 database."""
    import tempfile
    import hashlib
    import io
    import json
    import time
    import zipfile

    from sqlalchemy import func, select
    from sqlalchemy.engine import URL

    from plm_assistant.modules.audit.application.public import AuditService
    from plm_assistant.modules.audit.infrastructure.audit_repository import (
        SqlAlchemyAuditRepository,
    )
    from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
    from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow
    from plm_assistant.modules.platform.application.idempotency import IdempotencyScope
    from plm_assistant.modules.plugin.application.package_import_job_queue import (
        PluginPackageImportQueue,
    )
    from plm_assistant.modules.plugin.application.package_import_service import (
        PluginPackageImportError, PluginPackageImportService, SubmitPluginPackageImport,
    )
    from plm_assistant.modules.plugin.application.package_import_spool import (
        PluginPackageImportSpool,
    )
    from plm_assistant.modules.plugin.infrastructure.orm import (
        PluginPackageImportStagingRow,
    )
    from plm_assistant.modules.plugin.infrastructure.package_import_job_queue_repository import (
        SqlAlchemyPluginPackageImportQueueRepository,
    )
    from plm_assistant.modules.plugin.infrastructure.package_import_staging_repository import (
        SqlAlchemyPluginPackageImportStagingRepository,
    )
    from plm_assistant.modules.jobs.application.lease import JobLeaseService
    from plm_assistant.modules.jobs.infrastructure.lease_repository import (
        SqlAlchemyJobLeaseRepository,
    )
    from plm_assistant.modules.plugin.application.host_compatibility import (
        HostPlatformsPluginCompatibility,
    )
    from plm_assistant.modules.plugin.application.manifest_parser import PluginManifestParser
    from plm_assistant.modules.plugin.application.package_archive_inspector import (
        PluginPackageArchiveInspector,
    )
    from plm_assistant.modules.plugin.application.package_import_worker import (
        PluginPackageImportWorker,
    )
    from plm_assistant.modules.plugin.application.package_registration import (
        PluginPackageRegistrationService,
    )
    from plm_assistant.modules.plugin.application.signature_verifier import (
        PluginPackageSignatureVerifier, TrustedPluginSigner,
    )
    from plm_assistant.modules.plugin.infrastructure.orm import PluginPackageRow
    from plm_assistant.modules.plugin.infrastructure.package_import_worker_repository import (
        SqlAlchemyPluginPackageImportSource,
    )
    from plm_assistant.modules.plugin.infrastructure.package_registration_repository import (
        SqlAlchemyPluginPackageRegistrationRepository,
    )
    from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
    from plm_assistant.modules.platform.infrastructure.database import (
        create_database_runtime,
    )

    class SyntheticAdminAccess:
        def authorized_admin(self, transaction, *, session_token, now):
            assert len(session_token) == 32 and now.tzinfo is not None
            return actor_id

    class FailingAudit:
        def append(self, transaction, draft):
            raise RuntimeError("synthetic audit sink failure")

    fixture_db = context["fixture_db"]
    runtime = create_database_runtime(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=fixture_db.pg_port, database=fixture_db.database,
    ))
    audit = AuditService(SqlAlchemyAuditRepository())

    class SyntheticLicenseGuard:
        @staticmethod
        def require_valid(*, trace_id):
            assert isinstance(trace_id, uuid.UUID) and trace_id.int
            return object()

    license_guard = SyntheticLicenseGuard()
    test_root = Path(os.environ["PLM_P51_TEMP_ROOT"]).resolve()
    payload = b"PK" + bytes((3, 4)) + b" synthetic package import payload"
    signature = b"s" * 64
    signer_ref = "test-key:packaged-a08"
    digest = __import__("hashlib").sha256(payload).digest()
    with tempfile.TemporaryDirectory(prefix="a08-import-", dir=test_root) as storage_root:
        storage = LocalFileStorage(Path(storage_root))
        spool = PluginPackageImportSpool(storage=storage)
        queue = PluginPackageImportQueue(SqlAlchemyPluginPackageImportQueueRepository())
        staging = SqlAlchemyPluginPackageImportStagingRepository()

        def make_service(*, audit_service=audit):
            return PluginPackageImportService(
                unit_of_work=runtime.unit_of_work,
                spool=spool,
                queue=queue,
                staging_repository=staging,
                admin_access=SyntheticAdminAccess(),
                license_guard=license_guard,
                audit=audit_service,
            )

        scope = IdempotencyScope.from_key(
            actor_id=actor_id, project_id=None,
            operation="V1_PLUGIN_PACKAGE_IMPORT",
            key="a08-packaged-pg18-import-idempotency",
        )

        def command(*, content=payload, request_scope=scope,
                request_signature=signature, request_signer=signer_ref):
            return SubmitPluginPackageImport(
                scope=request_scope, session_token=b"a" * 32,
                trace_id=uuid.uuid4(), declared_length=len(content),
                declared_sha256=__import__("hashlib").sha256(content).digest(),
                detached_signature=request_signature, signer_key_ref=request_signer,
                chunks=(content[:5], content[5:]),
            )

        service = make_service()
        first = service.submit(command())
        replay = service.submit(command())
        if replay != first:
            raise AssertionError("A08 idempotent replay changed JobRef")
        files = [item for item in Path(storage_root).rglob("*") if item.is_file()]
        if len(files) != 1:
            raise AssertionError("A08 replay did not discard its duplicate staged file")

        with runtime.unit_of_work() as tx:
            session = tx.session
            job = session.execute(
                select(JobRow).where(JobRow.job_id == first.job_id)
            ).scalar_one()
            event = session.execute(
                select(OutboxEventRow).where(OutboxEventRow.event_id == first.event_id)
            ).scalar_one()
            metadata = session.execute(
                select(PluginPackageImportStagingRow).where(
                    PluginPackageImportStagingRow.package_upload_id == first.package_upload_id
                )
            ).scalar_one()
            audit_count = session.execute(
                select(func.count()).select_from(AuditEventRow).where(
                    AuditEventRow.action == "PLUGIN_PACKAGE_IMPORT_SUBMIT",
                    AuditEventRow.target_object_id == first.package_upload_id,
                )
            ).scalar_one()
            if (set(job.payload_refs) != {"package_upload_id", "sha256", "size_bytes"}
                    or job.payload_refs["sha256"] != digest.hex()
                    or event.payload_refs != {
                        "job_id": str(first.job_id),
                        "package_upload_id": str(first.package_upload_id),
                    }
                    or metadata.package_sha256 != digest
                    or metadata.package_size_bytes != len(payload)
                    or metadata.detached_signature != signature
                    or metadata.signer_key_ref != signer_ref
                    or audit_count != 1):
                raise AssertionError("A08 Job/Outbox/staging metadata/Audit facts diverged")
            if any(value in str(job.payload_refs).encode("utf-8")
                   for value in (payload, signature, signer_ref.encode("utf-8"))):
                raise AssertionError("A08 Job payload contains package or signature content")
            tx.commit()

        conflicting = b"PK" + bytes((3, 4)) + b" different payload"
        try:
            service.submit(command(content=conflicting))
        except PluginPackageImportError as exc:
            if exc.code != "CONFLICT_IDEMPOTENCY":
                raise
        else:
            raise AssertionError("A08 idempotency accepted different package content")

        before = {}
        with runtime.unit_of_work() as tx:
            session = tx.session
            for name, model in (
                ("jobs", JobRow), ("outbox", OutboxEventRow),
                ("staging", PluginPackageImportStagingRow),
            ):
                before[name] = session.execute(
                    select(func.count()).select_from(model).where(
                        model.owner_module == "plugin",
                    ) if name in {"jobs", "outbox"} else
                    select(func.count()).select_from(model)
                ).scalar_one()
            tx.commit()
        failing_scope = IdempotencyScope.from_key(
            actor_id=actor_id, project_id=None,
            operation="V1_PLUGIN_PACKAGE_IMPORT",
            key="a08-packaged-pg18-audit-rollback",
        )
        try:
            make_service(audit_service=FailingAudit()).submit(
                command(request_scope=failing_scope)
            )
        except PluginPackageImportError as exc:
            if exc.code != "JOB_STORE_UNAVAILABLE":
                raise
        else:
            raise AssertionError("A08 Audit failure did not abort import transaction")
        with runtime.unit_of_work() as tx:
            session = tx.session
            after = {
                "jobs": session.execute(
                    select(func.count()).select_from(JobRow).where(
                        JobRow.owner_module == "plugin",
                    )
                ).scalar_one(),
                "outbox": session.execute(
                    select(func.count()).select_from(OutboxEventRow).where(
                        OutboxEventRow.owner_module == "plugin",
                    )
                ).scalar_one(),
                "staging": session.execute(
                    select(func.count()).select_from(PluginPackageImportStagingRow)
                ).scalar_one(),
            }
            tx.commit()
        if after != before:
            raise AssertionError("A08 Audit rollback left partial PG import rows")
        # Run the actual fenced worker against PostgreSQL 18. One intentionally
        # untrusted package must fail closed; a synthetic signed archive may only
        # register verified metadata, and its entry point must remain unexecuted.
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        valid_signer_ref = "test-key:packaged-a08-worker"
        manifest = {
            "schema_version": "plm.plugin.manifest.v1",
            "plugin_id": "synthetic.a08worker",
            "name": "Synthetic A08 Worker",
            "version": "1.0.0",
            "plugin_api_version": "1.0.0",
            "supported_os": ["windows-11", "windows-server-2025", "debian-13"],
            "architecture": "x86_64",
            "entry_point": "plugin/main.py",
            "operations": [{"operation_id": "synthetic.read", "output_types": ["application/json"]}],
            "dependencies": [],
        }
        archive_stream = io.BytesIO()
        with zipfile.ZipFile(archive_stream, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", json.dumps(
                manifest, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8"))
            archive.writestr("plugin/main.py", b"raise RuntimeError('must not execute')\n")
        valid_archive = archive_stream.getvalue()
        valid_digest = hashlib.sha256(valid_archive).digest()
        signature_message = (
            b"PLM-PLUGIN-PACKAGE\x00v1\x00"
            + len(valid_signer_ref.encode("utf-8")).to_bytes(2, "big")
            + valid_signer_ref.encode("utf-8")
            + valid_digest
        )
        valid_signature = private_key.sign(signature_message)

        class SyntheticSignerResolver:
            def resolve_trusted_signer(self, signer_key_ref):
                if signer_key_ref != valid_signer_ref:
                    return None
                return TrustedPluginSigner(
                    signer_key_ref=valid_signer_ref, public_key_raw=public_key,
                )

        worker_repo = SqlAlchemyJobLeaseRepository()
        registration_service = PluginPackageRegistrationService(
            unit_of_work=runtime.unit_of_work,
            inspector=PluginPackageArchiveInspector(
                PluginManifestParser(),
                PluginPackageSignatureVerifier(SyntheticSignerResolver()),
            ),
            compatibility=HostPlatformsPluginCompatibility(),
            repository=SqlAlchemyPluginPackageRegistrationRepository(),
            audit=audit,
        )
        worker = PluginPackageImportWorker(
            unit_of_work=runtime.unit_of_work,
            leases=JobLeaseService(
                unit_of_work=runtime.unit_of_work, repository=worker_repo,
            ),
            lease_repository=worker_repo,
            source=SqlAlchemyPluginPackageImportSource(),
            storage=storage,
            registration=registration_service,
            license_guard=license_guard,
            worker_ref="a08-pg18-smoke-worker",
            lease_seconds=60,
        )
        failed_state = worker.run_once()
        with runtime.unit_of_work() as tx:
            failed_job = tx.session.execute(
                select(JobRow).where(JobRow.job_id == first.job_id)
            ).scalar_one()
            if failed_state != "FAILED" or failed_job.state != "FAILED":
                raise AssertionError("A08 untrusted package did not fail closed")
            tx.commit()

        valid_scope = IdempotencyScope.from_key(
            actor_id=actor_id, project_id=None,
            operation="V1_PLUGIN_PACKAGE_IMPORT",
            key="a08-packaged-pg18-worker-valid",
        )
        valid_job = service.submit(command(
            content=valid_archive, request_scope=valid_scope,
            request_signature=valid_signature, request_signer=valid_signer_ref,
        ))
        if worker.run_once() != "SUCCEEDED":
            raise AssertionError("A08 worker did not register the synthetic signed package")
        with runtime.unit_of_work() as tx:
            job_row = tx.session.execute(
                select(JobRow).where(JobRow.job_id == valid_job.job_id)
            ).scalar_one()
            package_row = tx.session.execute(
                select(PluginPackageRow).where(
                    PluginPackageRow.plugin_id_normalized == "synthetic.a08worker",
                    PluginPackageRow.plugin_version == "1.0.0",
                )
            ).scalar_one()
            registered_audits = tx.session.execute(
                select(func.count()).select_from(AuditEventRow).where(
                    AuditEventRow.action == "PLUGIN_PACKAGE_REGISTER",
                    AuditEventRow.target_object_id == package_row.plugin_package_id,
                )
            ).scalar_one()
            if (job_row.state != "SUCCEEDED" or package_row.package_state != "VERIFIED"
                    or package_row.package_sha256 != valid_digest or registered_audits != 1):
                raise AssertionError("A08 worker Job/package/Audit facts diverged")
            tx.commit()

        # Exercise a bounded retry on a transient staging read failure, then
        # restore the exact synthetic file and allow the fenced generation to finish.
        retry_scope = IdempotencyScope.from_key(
            actor_id=actor_id, project_id=None,
            operation="V1_PLUGIN_PACKAGE_IMPORT",
            key="a08-packaged-pg18-worker-retry",
        )
        retry_job = service.submit(command(
            content=valid_archive, request_scope=retry_scope,
            request_signature=valid_signature, request_signer=valid_signer_ref,
        ))
        retry_locator, _ = storage.locators(
            scope="GLOBAL", project_id=None, file_object_id=retry_job.package_upload_id,
        )
        staged_path = Path(storage_root).joinpath(*retry_locator.split("/"))
        held_path = staged_path.with_name(staged_path.name + ".temporarily-held")
        staged_path.replace(held_path)
        retry_state = worker.run_once()
        held_path.replace(staged_path)
        if retry_state != "RETRY_WAIT":
            raise AssertionError("A08 transient staging failure did not enter bounded retry")
        time.sleep(5.2)
        if worker.run_once() != "SUCCEEDED":
            raise AssertionError("A08 bounded retry did not complete after staging recovery")
        with runtime.unit_of_work() as tx:
            retry_row = tx.session.execute(
                select(JobRow).where(JobRow.job_id == retry_job.job_id)
            ).scalar_one()
            if retry_row.state != "SUCCEEDED" or retry_row.attempt_count != 2:
                raise AssertionError("A08 retry did not advance its fenced attempt")
            tx.commit()

        files = [item for item in Path(storage_root).rglob("*") if item.is_file()]
        if len(files) != 3:
            raise AssertionError("A08 worker smoke changed the staged package count")
    runtime.dispose()
    print("PLG_01_A08_PACKAGE_IMPORT_PG18_PASS: atomic upload; scoped claim; terminal signature rejection; "
          "verified metadata registration; bounded retry recovery; Audit rollback",
          flush=True)

def packaged_planversion_probe(**context) -> None:
    # Reuse the P51 disposable project and account, but do not make PlanVersion
    # acceptance depend on the unrelated Prototype Package catalog UI.
    fixture_db = context["fixture_db"]
    project = context["project"]
    with fixture_db() as db:
        db.execute("DELETE FROM plm.auth_login_rate_buckets")
        actor_row = db.execute(
            "SELECT user_id FROM plm.auth_users "
            "WHERE username_normalized='synthetic packaged user'"
        ).fetchone()
        assert actor_row is not None, "synthetic package manager missing"
        actor = actor_row[0]
        membership = db.execute(
            "SELECT project_role,state FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        ).fetchone()
        assert membership is not None and membership[0] in {
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }, membership
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s", (project,))
            db.execute(
                "UPDATE plm.prj_project_members SET state='ACTIVE',effective_at="
                "statement_timestamp(),ended_at=NULL WHERE project_id=%s AND user_id=%s",
                (project, actor),
            )
            db.execute(
                "UPDATE plm.prj_departments d SET state='ACTIVE' FROM plm.prj_project_members m "
                "WHERE m.project_id=%s AND m.user_id=%s AND d.department_id=m.department_id",
                (project, actor),
            )
    context["user_id"] = actor
    requirement, requirement_version, _source_document, document_version = (
        a05["seed_current_requirement"](context, project))

    # P05 verifies Requirement-owned exact-version reads under real PostgreSQL
    # authorization before the composition root maps the owner DTO to Output.
    from sqlalchemy.engine import URL
    from plm_assistant.entrypoints.output_requirement_source_adapter import (
        RequirementOutputSourceAdapter,
    )
    from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
    from plm_assistant.modules.project.infrastructure.authorization_repository import (
        SqlAlchemyProjectAuthorizationRepository,
    )
    from plm_assistant.modules.requirement.application.read_versions import (
        RequirementVersionReadError, RequirementVersionReadService,
    )
    from plm_assistant.modules.requirement.infrastructure.version_read_repository import (
        SqlAlchemyRequirementVersionReadRepository,
    )
    from plm_assistant.modules.platform.infrastructure.database import create_database_runtime

    source_runtime = create_database_runtime(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=fixture_db.pg_port, database=fixture_db.database,
    ))
    source_reader = RequirementVersionReadService(
        unit_of_work=source_runtime.unit_of_work,
        access=object(), license_guard=object(),
        authorization=ProjectAuthorizationService(
            unit_of_work=source_runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ),
        repository=SqlAlchemyRequirementVersionReadRepository(),
    )
    source_adapter = RequirementOutputSourceAdapter(source_reader)
    with source_runtime.unit_of_work() as tx:
        source = source_adapter.read_authorized_fixed_version(
            tx, actor_id=actor, project_id=project,
            source_version_ref=requirement_version,
        )
        tx.commit()
    if (source.source_version_ref != requirement_version
            or source.project_id != project
            or source.source_kind != "REQUIREMENT_VERSION"
            or source.review_state != "APPROVED"
            or source.fields.get("statement") != "项目应形成可追溯的受控原型评审记录"):
        raise AssertionError("OUT-01-A01-P05 exact Requirement source projection mismatch")
    try:
        with source_runtime.unit_of_work() as tx:
            source_adapter.read_authorized_fixed_version(
                tx, actor_id=uuid.uuid4(), project_id=project,
                source_version_ref=requirement_version,
            )
    except RequirementVersionReadError:
        pass
    else:
        raise AssertionError("OUT-01-A01-P05 accepted a non-member actor")
    source_runtime.dispose()
    print("OUT_01_A01_P05_REQUIREMENT_FIXED_SOURCE_PG_PASS: scoped/versioned/authorized",
          flush=True)

    from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
        BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID, BuiltinOutputTemplateRegistry,
    )
    packaged_template = BuiltinOutputTemplateRegistry().get_immutable_version(
        None, template_version_ref=BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
    )
    if (packaged_template is None or packaged_template.output_type != "DOCX"
            or packaged_template.source_kinds != ("REQUIREMENT_VERSION",)
            or packaged_template.immutable is not True
            or packaged_template.published is not True):
        raise AssertionError("OUT-01-A01-P07 packaged builtin template mismatch")
    print("OUT_01_A01_P07_BUILTIN_TEMPLATE_REGISTRY_PASS: fixed-ref/immutable",
          flush=True)

    from plm_assistant.modules.output.infrastructure.builtin_policy_registry import (
        BUILTIN_REQUIREMENT_DOCX_POLICY_REF, BuiltinOutputPolicyRegistry,
    )
    packaged_policy = BuiltinOutputPolicyRegistry().get_policy(
        None, policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF,
    )
    if (packaged_policy is None
            or packaged_policy.allowed_template_versions != (
                BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,)
            or packaged_policy.allowed_output_types != ("DOCX",)
            or packaged_policy.allowed_review_states != ("APPROVED",)
            or dict(packaged_policy.fields_by_source_kind) != {
                "REQUIREMENT_VERSION": (
                    "title", "statement", "acceptance_criteria",
                ),
            }
            or packaged_policy.max_sources != 4
            or packaged_policy.max_context_bytes != 8192):
        raise AssertionError("OUT-01-A01-P09 packaged policy mismatch")
    print("OUT_01_A01_P09_BUILTIN_POLICY_REGISTRY_PASS: fixed-ref/allowlist",
          flush=True)
    with fixture_db() as db:
        approved = db.execute(
            "SELECT 1 FROM plm.sol_outlines WHERE project_id=%s "
            "AND current_approved_version_ref IS NOT NULL LIMIT 1", (project,),
        ).fetchone()
    if approved is None:
        from sqlalchemy.engine import URL

        from plm_assistant.entrypoints.windows_license_runtime import (
            _assemble as assemble_license_services,
        )
        from plm_assistant.entrypoints.windows_trusted_time import (
            create_windows_trusted_time_integrity,
        )
        from plm_assistant.modules.audit.application.public import AuditService
        from plm_assistant.modules.audit.infrastructure.audit_repository import (
            SqlAlchemyAuditRepository,
        )
        from plm_assistant.modules.auth.infrastructure.deployment_read_access import (
            SqlAlchemyDeploymentReadAccess,
        )
        from plm_assistant.modules.auth.infrastructure.project_read_access import (
            SqlAlchemyProjectReadAccess,
        )
        from plm_assistant.modules.document.application.prepare_download import (
            PrepareDownloadService,
        )
        from plm_assistant.modules.document.application.read_documents import (
            DocumentReadService,
        )
        from plm_assistant.modules.document.application.read_parse_result import (
            DocumentParseResultReadService,
        )
        from plm_assistant.modules.document.infrastructure.local_storage import (
            LocalFileStorage,
        )
        from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
            SqlAlchemyParseResultReadRepository,
        )
        from plm_assistant.modules.document.infrastructure.parse_result_storage import (
            LocalParseResultStorage,
        )
        from plm_assistant.modules.document.infrastructure.read_repository import (
            SqlAlchemyDocumentReadRepository,
        )
        from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
            BootstrapSettings,
        )
        from plm_assistant.modules.platform.infrastructure.database import (
            create_database_runtime,
        )
        from plm_assistant.modules.license.infrastructure.packaged_product_key import (
            PackagedProductKey,
        )
        from plm_assistant.modules.license.infrastructure.windows_selected_machine import (
            WindowsSelectedMachine,
        )
        from plm_assistant.modules.project.infrastructure.authorization_repository import (
            SqlAlchemyProjectAuthorizationRepository,
        )

        runtime = create_database_runtime(URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=fixture_db.pg_port, database=fixture_db.database,
        ))
        settings = BootstrapSettings(
            data_root=Path(fixture_db.data_root),
            selected_mac=context["selected_mac"],
            trusted_origins=(context["origin"],),
        )
        licenses = assemble_license_services(
            runtime, product=PackagedProductKey(
                read_manifest=lambda: Path(
                    fixture_db.product_public_key_file,
                ).read_bytes(),
            ),
            machine=WindowsSelectedMachine(settings.selected_mac),
            integrity=create_windows_trusted_time_integrity(),
        )
        audit = AuditService(SqlAlchemyAuditRepository())
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=licenses.guard,
            repository=SqlAlchemyDocumentReadRepository(),
        )
        downloads = PrepareDownloadService(
            reader=documents, storage=LocalFileStorage(settings.data_root),
            unit_of_work=runtime.unit_of_work, audit=audit,
        )
        parse_results = DocumentParseResultReadService(
            documents=downloads,
            metadata=SqlAlchemyParseResultReadRepository(),
            storage=LocalParseResultStorage(settings.data_root),
            unit_of_work=runtime.unit_of_work,
        )
        context.update({
            "runtime": runtime, "audit": audit,
            "license_guard": licenses.guard, "documents": documents,
            "downloads": downloads, "parse_results": parse_results,
        })
        # Build a single approved Section through production Owners in this
        # disposable package-smoke database; no approval-state SQL seeding.
        with fixture_db() as db:
            evidence_row = db.execute(
                "SELECT evidence_id FROM plm.evd_evidence_records "
                "WHERE project_id=%s AND display_label='Synthetic Project Handover Evidence' "
                "AND eligibility_state='ELIGIBLE'", (project,),
            ).fetchone()
        assert evidence_row is not None, "packaged synthetic Evidence source missing"
        try:
            manager_token, manager_csrf = _approved_section_fixture(
                context, project=project, actor=actor,
                requirement=requirement, requirement_version=requirement_version,
                document_version=document_version, evidence=evidence_row[0],
            )
        except Exception:
            runtime.dispose()
            raise
        # The enclosing Handover probe keeps an unrelated observer client; use
        # the matched Manager Session created through production Login HTTP.
        token, csrf = manager_token, manager_csrf
        try:
            outline_fixture = plan_edge["owner"].full
            # The source fixture historically targets a database named
            # "postgres"; the packaged smoke creates a unique disposable DB.
            # Bind only this in-memory fixture module to that owned DB.
            outline_fixture._connection = lambda port: {
                "host": "127.0.0.1", "port": port, "user": "poc_admin",
                "dbname": fixture_db.database,
            }
            outline_context = context | {
                "port": fixture_db.pg_port,
                "runtime": runtime, "manager": actor, "token": token,
                "csrf": csrf, "license_guard": licenses.guard,
                "audit": audit, "documents": documents,
                "downloads": downloads, "parse_results": parse_results,
            }
            outline_fixture._outline_full(**outline_context)
            # Validation leaves the new Outline in DRAFT after exercising its
            # positive/negative facts. PlanVersion needs a genuinely approved
            # source, so use the existing Owner's real Review API fixture.
            owner_fixture = plan_edge["owner"]
            original_connection = owner_fixture._connection
            owner_fixture._connection = lambda port: {
                "host": "127.0.0.1", "port": port, "user": "poc_admin",
                "dbname": fixture_db.database,
            }
            try:
                owner_fixture._restore_coverage_edge(outline_context)
                owner_fixture._approve_current_outline(
                    outline_context, Path(fixture_db.data_root))
            finally:
                owner_fixture._connection = original_connection
        finally:
            runtime.dispose()
    with fixture_db() as db:
        assert db.execute(
            "SELECT 1 FROM plm.sol_outlines WHERE project_id=%s "
            "AND current_approved_version_ref IS NOT NULL LIMIT 1", (project,),
        ).fetchone(), "synthetic Approved Outline source fixture unavailable"

    env = os.environ.copy()
    env.update({
        "PLM_P51_A17_MANAGER": "Synthetic Packaged User",
        "PLM_P51_A17_REVIEWER": "Synthetic Handover Customer",
        "PLM_P51_A17_PASSWORD": "synthetic-packaged-login-password",
        "PLM_P51_A17_TEMP": str(Path(os.environ["PLM_P51_TEMP_ROOT"]).resolve()),
    })
    edge = subprocess.run(
        ["node", str(ROOT / "validation/plt-pkg-01-a09-p51-a17-planversion-packaged/run-edge-browser.mjs"),
         context["origin"], str(project)],
        cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=360, check=False,
    )
    if edge.returncode or "P51_A17_PACKAGED_PLANVERSION_EDGE_PASS" not in edge.stdout:
        raise AssertionError("packaged PlanVersion Edge flow failed: " + edge.stdout[-12000:])
    print(edge.stdout.strip(), flush=True)
    match = __import__("re").search(r"plan=([0-9a-f-]{36}); version=([0-9a-f-]{36})", edge.stdout)
    assert match, "PlanVersion browser result identities missing"
    plan_id, version_id = map(uuid.UUID, match.groups())
    with fixture_db() as db:
        plan = db.execute(
            "SELECT plan_state FROM plm.pln_plans WHERE plan_id=%s AND project_id=%s",
            (plan_id, project),
        ).fetchone()
        version = db.execute(
            "SELECT version_state,review_ref FROM plm.pln_plan_versions "
            "WHERE plan_version_id=%s AND project_id=%s", (version_id, project),
        ).fetchone()
        counts = db.execute(
            "SELECT (SELECT count(*) FROM plm.pln_wbs_items WHERE plan_version_id=%s),"
            "(SELECT count(*) FROM plm.pln_item_requirement_refs WHERE plan_version_id=%s),"
            "(SELECT count(*) FROM plm.pln_plan_version_validation_results WHERE plan_version_id=%s)",
            (version_id, version_id, version_id),
        ).fetchone()
        review = db.execute(
            "SELECT review_state,active_round_id FROM plm.rvw_reviews WHERE review_id=%s",
            (version[1],),
        ).fetchone() if version and version[1] else None
        round_state = db.execute(
            "SELECT round_state FROM plm.rvw_review_rounds WHERE review_round_id=%s",
            (review[1],),
        ).fetchone() if review else None
        decisions = db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_round_id=%s",
            (review[1],),
        ).fetchone()[0] if review else -1
    if (plan != ("ACTIVE",) or not version or version[0] != "IN_REVIEW"
            or counts != (2, 2, 1) or not review or review[0] != "IN_REVIEW"
            or not round_state or round_state[0] != "IN_REVIEW" or decisions != 0):
        raise AssertionError(
            f"packaged PlanVersion PG state mismatch: plan={plan}, version={version}, "
            f"children={counts}, review={review}, round={round_state}, decisions={decisions}"
        )
    print(f"P51_A17_PACKAGED_PLANVERSION_PG_PASS: state={version[0]}; "
          f"WBS/requirement/validation={counts}; Review/Round={review[0]}/{round_state[0]}; decisions=0",
          flush=True)
    _plugin_package_import_pg_smoke(context, actor_id=actor)


a05["prototype_probe"].__globals__["prototype_probe"] = packaged_planversion_probe


if __name__ == "__main__":
    test_temp = Path(os.environ["PLM_P51_TEMP_ROOT"]).resolve()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if (not test_temp.is_absolute() or test_temp.drive.upper() == "C:"
            or not str(test_temp).isascii() or runner_temp.drive.upper() == "C:"
            or runner_temp not in test_temp.parents or test_temp.name != "PLMToolTemp"):
        raise ValueError("P51 temporary root must be an ASCII non-C RUNNER_TEMP descendant named PLMToolTemp")
    test_temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(test_temp)
    os.environ["TMP"] = str(test_temp)
    os.environ["PLM_TEST_TEMP_ROOT"] = str(test_temp)
    import tempfile
    tempfile.tempdir = None
    sys.exit(a05["main"]())
