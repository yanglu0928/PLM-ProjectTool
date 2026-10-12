"""Real disposable PG18 proof of current Requirement→Section IMPLEMENTS coverage."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.solution.application.read_section_version import SectionVersionReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.trace.application.create_link import CreateTraceLinkRefs, TraceCreateService
from plm_assistant.modules.trace.application.implements_coverage import TraceImplementsCoverageError, TraceImplementsCoverageService
from plm_assistant.modules.trace.application.revoke_link import RevokeTraceLink, TraceRevokeService
from plm_assistant.modules.trace.application.target_proof import TraceProofQuery, TracePublicEdgeResolver, TraceResourceVersionRef, TraceTargetProofService
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef
from plm_assistant.modules.trace.infrastructure.create_repository import SqlAlchemyTraceCreateRepository
from plm_assistant.modules.trace.infrastructure.cycle_guard import SqlAlchemyTraceCycleGuard
from plm_assistant.modules.trace.infrastructure.implements_repository import SqlAlchemyTraceImplementsRepository
from plm_assistant.modules.trace.infrastructure.revoke_repository import SqlAlchemyTraceRevokeRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_create_for_implements",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def denied(action):
    try:
        action()
    except TraceImplementsCoverageError as error:
        assert error.code == "TRACE_COVERAGE_REQUIRED", error.code
    else:
        raise AssertionError("expected current IMPLEMENTS coverage denial")


def on_coverage(*, port, runtime, license_guard, audit, project, other_project,
                token, csrf, section, requirement, requirement_version,
                **_unused):
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    requirement_owner = RequirementVersionTraceOwner(RequirementVersionReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=authorization,
        repository=SqlAlchemyRequirementVersionReadRepository(),
    ))
    section_owner = SectionVersionTraceOwner(SectionVersionReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=authorization,
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
    ))
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
            "REQ-03": requirement_owner, "SOL-05": section_owner,
        }),
    )
    revoker = TraceRevokeService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
        license_guard=license_guard,
        repository=SqlAlchemyTraceRevokeRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    coverage = TraceImplementsCoverageService(
        repository=SqlAlchemyTraceImplementsRepository(), owners=proofs)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s AND version_no=1", (section,),
        ).fetchone()[0]
    requirement_ref = TraceVersionRef("requirement", "REQ-03", requirement,
                                      requirement_version, "PROJECT", project)
    section_ref = TraceVersionRef("solution", "SOL-05", section, version,
                                  "PROJECT", project)
    query = TraceProofQuery(token, uuid.uuid4())

    def prove(expected=(requirement_ref,)):
        with runtime.unit_of_work() as tx:
            return coverage.prove(tx, query=query, section=section_ref,
                                  requirement_refs=expected)

    denied(prove)
    created = creator.create_refs(CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project,
        TraceResourceVersionRef("REQ-03", requirement, requirement_version),
        TraceResourceVersionRef("SOL-05", section, version), "IMPLEMENTS",
    ), idempotency_key="implements-create-001")
    assert prove().trace_link_ids == (created.trace_link_id,)
    denied(lambda: prove((TraceVersionRef(
        "requirement", "REQ-03", requirement, uuid.uuid4(),
        "PROJECT", project),)))
    with runtime.unit_of_work() as tx:
        denied(lambda: coverage.prove(
            tx, query=query, section=section_ref,
            requirement_refs=(TraceVersionRef(
                "requirement", "REQ-03", requirement, requirement_version,
                "PROJECT", other_project),)))
    revoked = revoker.revoke(RevokeTraceLink(
        token, csrf, uuid.uuid4(), project, created.trace_link_id, 0,
    ), idempotency_key="implements-revoke-001")
    assert revoked.trace_link_id == created.trace_link_id
    denied(prove)
    recreated = creator.create_refs(CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project,
        TraceResourceVersionRef("REQ-03", requirement, requirement_version),
        TraceResourceVersionRef("SOL-05", section, version), "IMPLEMENTS",
    ), idempotency_key="implements-create-002")
    assert recreated.trace_link_id != created.trace_link_id
    assert prove().trace_link_ids == (recreated.trace_link_id,)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        states = db.execute(
            "SELECT link_state FROM plm.trc_links WHERE target_version_id=%s "
            "ORDER BY trace_link_id", (version,),
        ).fetchall()
        assert sorted(state[0] for state in states) == ["ACTIVE", "REVOKED"]
    print("TRC_01_A03_P03_IMPLEMENTS_PG_PASS: real create, exact fixed set, old version rejection, revoke denial and new active replacement")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_coverage))
