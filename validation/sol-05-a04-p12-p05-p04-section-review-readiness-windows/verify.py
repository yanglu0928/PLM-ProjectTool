"""Disposable Win11/PG18 exact Trace + current Spec readiness observation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_version_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.solution.application.read_section_version import SectionVersionReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.trace.application.create_link import CreateTraceLinkRefs, TraceCreateService
from plm_assistant.modules.trace.application.revoke_link import RevokeTraceLink, TraceRevokeService
from plm_assistant.modules.trace.application.target_proof import TracePublicEdgeResolver, TraceResourceVersionRef, TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.create_repository import SqlAlchemyTraceCreateRepository
from plm_assistant.modules.trace.infrastructure.cycle_guard import SqlAlchemyTraceCycleGuard
from plm_assistant.modules.trace.infrastructure.revoke_repository import SqlAlchemyTraceRevokeRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_readiness_fit_fixture",
    ROOT / "validation/sol-05-a04-p12-p04-p02-spec-fit-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
fixture = prior.fixture
_fit_owner = prior._after_submit


def _after_submit(*, port, runtime, project, draft, token, csrf, audit,
                  license_guard, documents, downloads, parse_results, **context):
    _fit_owner(
        port=port, runtime=runtime, project=project, draft=draft,
        token=token, csrf=csrf, audit=audit, license_guard=license_guard,
        documents=documents, downloads=downloads,
        parse_results=parse_results, **context)
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres")
    with psycopg.connect(**connection) as db:
        section, version, requirement, req_version = db.execute(
            "SELECT v.solution_section_id,v.solution_section_version_id,"
            "r.requirement_id,r.requirement_version_id "
            "FROM plm.sol_section_versions v "
            "JOIN plm.sol_section_spec_refs s ON "
            "s.solution_section_version_id=v.solution_section_version_id "
            "JOIN plm.sol_section_requirement_refs r ON "
            "r.solution_section_version_id=v.solution_section_version_id "
            "WHERE v.project_id=%s AND s.fit_rationale IS NOT NULL",
            (project,)).fetchone()
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    read_access = SqlAlchemyProjectReadAccess()
    requirement_owner = RequirementVersionTraceOwner(RequirementVersionReadService(
        unit_of_work=runtime.unit_of_work, access=read_access,
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyRequirementVersionReadRepository()))
    section_owner = SectionVersionTraceOwner(SectionVersionReadService(
        unit_of_work=runtime.unit_of_work, access=read_access,
        license_guard=license_guard, authorization=authorization,
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository()))
    proofs = TraceTargetProofService({
        ("requirement", "REQ-03"): requirement_owner,
        ("solution", "SOL-05"): section_owner,
    })
    creator = TraceCreateService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
        license_guard=license_guard, proofs=proofs,
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
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_section_version_validate_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    path = (f"/api/v1/projects/{project}/solution-sections/{section}"
            f"/versions/{version}:validate")
    def headers(key):
        return {"cookie": "plm_session=" + token.hex(),
                "origin": "https://plm.example.test",
                "x-csrf-token": csrf.hex(), "idempotency-key": key}
    with TestClient(create_app(solution_section_version_validate_router=router),
                    base_url="https://plm.example.test") as app:
        missing = app.post(path, headers=headers("section-readiness-no-edge-0001"))
        assert missing.status_code == 200, missing.text
        assert missing.json()["data"]["facts"]["spec"] == "PASS"
        assert missing.json()["data"]["facts"]["trace"] == "FAIL"
        assert not missing.json()["data"]["ready_for_review"]
        edge = creator.create_refs(CreateTraceLinkRefs(
            token, csrf, uuid.uuid4(), project,
            TraceResourceVersionRef("REQ-03", requirement, req_version),
            TraceResourceVersionRef("SOL-05", section, version), "IMPLEMENTS"),
            idempotency_key="section-readiness-edge-0001")
        ready = app.post(path, headers=headers("section-readiness-ready-0001"))
        assert ready.status_code == 200, ready.text
        first = ready.json()["data"]
        assert set(first["facts"].values()) == {"PASS"}, first
        assert first["valid"] and first["ready_for_review"]
        revoker.revoke(RevokeTraceLink(
            token, csrf, uuid.uuid4(), project, edge.trace_link_id, 0),
            idempotency_key="section-readiness-revoke-0001")
        revoked = app.post(path, headers=headers("section-readiness-revoked-0001"))
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["data"]["facts"]["trace"] == "FAIL"
        assert revoked.json()["data"]["facts"]["spec"] == "PASS"
        assert not revoked.json()["data"]["ready_for_review"]
        replay = app.post(path, headers=headers("section-readiness-ready-0001"))
        assert replay.status_code == 200 and replay.json()["data"] == first
    with psycopg.connect(**connection) as db:
        state = db.execute(
            "SELECT version_state FROM plm.sol_section_versions "
            "WHERE solution_section_version_id=%s", (version,)).fetchone()[0]
        assert state == "DRAFT"  # readiness did not create Review or approve.
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_SECTION_VERSION_VALIDATED' AND target_version_id=%s",
            (version,)).fetchone()[0] == 3
    print("SOL_05_A04_P12_P05_P04_SECTION_READY_WINDOWS_PASS: exact current "
          "Trace+Spec ready, revocation blocks new key, old key replays")


if __name__ == "__main__":
    fixture._after_submit = _after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
