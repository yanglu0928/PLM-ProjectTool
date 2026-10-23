"""Disposable Win11/PG18 Section Review submit with current Trace+Spec."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.trace_requirement_owner import (
    RequirementVersionTraceOwner,
)
from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_review_submission_router,
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
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementVersionReadService,
)
from plm_assistant.modules.requirement.infrastructure.version_read_repository import (
    SqlAlchemyRequirementVersionReadRepository,
)
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionReadService,
)
from plm_assistant.modules.solution.infrastructure.section_read_repository import (
    SqlAlchemySectionReadRepository,
)
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)
from plm_assistant.modules.trace.application.create_link import (
    CreateTraceLinkRefs, TraceCreateService,
)
from plm_assistant.modules.trace.application.revoke_link import (
    RevokeTraceLink, TraceRevokeService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TracePublicEdgeResolver, TraceResourceVersionRef,
    TraceTargetProofService,
)
from plm_assistant.modules.trace.infrastructure.create_repository import (
    SqlAlchemyTraceCreateRepository,
)
from plm_assistant.modules.trace.infrastructure.cycle_guard import (
    SqlAlchemyTraceCycleGuard,
)
from plm_assistant.modules.trace.infrastructure.revoke_repository import (
    SqlAlchemyTraceRevokeRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_submit_sources",
    ROOT / "validation/sol-05-a04-p12-p05-p04-section-review-readiness-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _seed_customer(*, db, project: uuid.UUID) -> uuid.UUID:
    reviewer, credential = uuid.uuid4(), uuid.uuid4()
    department = db.execute(
        "SELECT department_id FROM plm.prj_departments "
        "WHERE project_id=%s LIMIT 1", (project,)).fetchone()
    department_id = department[0] if department else uuid.uuid4()
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        if department is None:
            db.execute(
                "INSERT INTO plm.prj_departments(department_id,project_id,"
                "department_code,department_code_normalized,name) "
                "VALUES (%s,%s,'CUSTOMER','customer','Customer Team')",
                (department_id, project))
        db.execute(
            "INSERT INTO plm.auth_users(user_id,username_display,"
            "username_normalized,state,credential_version,"
            "active_password_credential_id) VALUES "
            "(%s,'Synthetic Customer','synthetic customer','ENABLED',1,%s)",
            (reviewer, credential))
        db.execute(
            "INSERT INTO plm.auth_password_credentials("
            "password_credential_id,user_id,credential_version,password_hash,"
            "algorithm_id,parameter_set) "
            "VALUES (%s,%s,1,'synthetic-hash','SCRYPT','{}')",
            (credential, reviewer))
        db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,"
            "department_id,project_role) VALUES "
            "(%s,%s,%s,'CUSTOMER_MEMBER')",
            (project, reviewer, department_id))
    return reviewer


def _trace_services(*, runtime, license_guard, audit):
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    access = SqlAlchemyProjectReadAccess()
    requirement_owner = RequirementVersionTraceOwner(
        RequirementVersionReadService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyRequirementVersionReadRepository()))
    section_owner = SectionVersionTraceOwner(SectionVersionReadService(
        unit_of_work=runtime.unit_of_work, access=access,
        license_guard=license_guard, authorization=authorization,
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository()))
    owners = TraceTargetProofService({
        ("requirement", "REQ-03"): requirement_owner,
        ("solution", "SOL-05"): section_owner,
    })
    creator = TraceCreateService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
        license_guard=license_guard, proofs=owners,
        cycle_guard=SqlAlchemyTraceCycleGuard(),
        repository=SqlAlchemyTraceCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        public_resolver=TracePublicEdgeResolver({
            "REQ-03": requirement_owner, "SOL-05": section_owner}))
    revoker = TraceRevokeService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
        license_guard=license_guard,
        repository=SqlAlchemyTraceRevokeRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    return creator, revoker


def _after_submit(*, port, runtime, project, draft, token, csrf, audit,
                  license_guard, documents, downloads, parse_results,
                  **context):
    # Reuse the synthetic approved Spec + author fit fixture, not customer data.
    prior._fit_owner(
        port=port, runtime=runtime, project=project, draft=draft,
        token=token, csrf=csrf, audit=audit,
        license_guard=license_guard, documents=documents,
        downloads=downloads, parse_results=parse_results, **context)
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres")
    with psycopg.connect(**connection) as db:
        section, version, requirement, req_version = db.execute(
            "SELECT v.solution_section_id,v.solution_section_version_id,"
            "r.requirement_id,r.requirement_version_id "
            "FROM plm.sol_section_versions v JOIN "
            "plm.sol_section_spec_refs s ON "
            "s.solution_section_version_id=v.solution_section_version_id "
            "JOIN plm.sol_section_requirement_refs r ON "
            "r.solution_section_version_id=v.solution_section_version_id "
            "WHERE v.project_id=%s AND s.fit_rationale IS NOT NULL "
            "ORDER BY v.version_no DESC LIMIT 1", (project,)).fetchone()
        reviewer = _seed_customer(db=db, project=project)
        manager = db.execute(
            "SELECT m.user_id FROM plm.prj_project_members m "
            "JOIN plm.auth_sessions s ON s.user_id=m.user_id "
            "WHERE m.project_id=%s AND m.project_role='PROJECT_MANAGER' "
            "AND m.state='ACTIVE' LIMIT 1", (project,)).fetchone()[0]
    creator, revoker = _trace_services(
        runtime=runtime, license_guard=license_guard, audit=audit)
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_section_review_submission_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    path = (f"/api/v1/projects/{project}/solution-sections/{section}/"
            f"versions/{version}:submit-review")
    body = {"reviewer_ids": [str(reviewer)],
            "policy_ref": "SOLUTION_SECTION_ALL_V1",
            "due_at": None, "submission_note": None}

    def headers(key):
        return {"cookie": "plm_session=" + token.hex(),
                "origin": "https://plm.example.test",
                "x-csrf-token": csrf.hex(), "idempotency-key": key}

    with TestClient(create_app(
            solution_section_review_submission_router=router),
            base_url="https://plm.example.test") as app:
        missing = app.post(path, headers=headers("section-no-trace-0001"),
                           json=body)
        assert missing.status_code == 422, missing.text
        first_edge = creator.create_refs(CreateTraceLinkRefs(
            token, csrf, uuid.uuid4(), project,
            TraceResourceVersionRef("REQ-03", requirement, req_version),
            TraceResourceVersionRef("SOL-05", section, version),
            "IMPLEMENTS"), idempotency_key="section-first-edge-0001")
        revoker.revoke(RevokeTraceLink(
            token, csrf, uuid.uuid4(), project,
            first_edge.trace_link_id, 0),
            idempotency_key="section-first-revoke-0001")
        revoked = app.post(path, headers=headers("section-revoked-0001"),
                           json=body)
        assert revoked.status_code == 422, revoked.text
        creator.create_refs(CreateTraceLinkRefs(
            token, csrf, uuid.uuid4(), project,
            TraceResourceVersionRef("REQ-03", requirement, req_version),
            TraceResourceVersionRef("SOL-05", section, version),
            "IMPLEMENTS"), idempotency_key="section-restored-edge-0001")
        not_customer = app.post(
            path, headers=headers("section-not-customer-0001"),
            json={**body, "reviewer_ids": [str(manager)]})
        assert not_customer.status_code == 422, not_customer.text
        wrong_project = app.post(
            path.replace(str(project), str(uuid.uuid4())),
            headers=headers("section-cross-project-0001"), json=body)
        assert wrong_project.status_code == 404, wrong_project.text
        accepted = app.post(path, headers=headers("section-review-0001"),
                            json=body)
        assert accepted.status_code == 201, accepted.text
        data = accepted.json()["data"]
        assert data["state"] == "IN_REVIEW"
        replay = app.post(path, headers=headers("section-review-0001"),
                          json=body)
        assert replay.status_code == 201 and replay.json()["data"] == data
    with psycopg.connect(**connection) as db:
        state = db.execute(
            "SELECT version_state,review_ref,review_round_ref "
            "FROM plm.sol_section_versions WHERE "
            "solution_section_version_id=%s", (version,)).fetchone()
        assert state == (
            "IN_REVIEW", uuid.UUID(data["review_id"]),
            uuid.UUID(data["review_round_id"]))
        assert db.execute(
            "SELECT count(*) FROM plm.sol_section_review_state_results "
            "WHERE solution_section_version_id=%s AND event_type='START'",
            (version,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SECTION_VERSION_SUBMIT_REVIEW' "
            "AND result_ref_id=%s",
            (uuid.UUID(data["review_round_id"]),)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_STARTED' "
            "AND target_object_id=%s",
            (uuid.UUID(data["review_round_id"]),)).fetchone()[0] == 1
    print("SOL_05_A04_P13_P05_P03_SECTION_REVIEW_SUBMIT_WINDOWS_PASS")


if __name__ == "__main__":
    fixture = prior.fixture
    fixture._after_submit = _after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
