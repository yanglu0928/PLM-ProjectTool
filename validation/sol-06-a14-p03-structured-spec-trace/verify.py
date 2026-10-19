"""Win11/PG18 proof of exact Requirement -> SOL-06 IMPLEMENTS coverage."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from plm_assistant.entrypoints.trace_requirement_owner import (
    RequirementVersionTraceOwner,
)
from plm_assistant.entrypoints.trace_structured_spec_owner import (
    StructuredSpecTraceOwner,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
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
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementVersionReadService,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.requirement.infrastructure.version_read_repository import (
    SqlAlchemyRequirementVersionReadRepository,
)
from plm_assistant.modules.solution.application.evaluate_structured_spec_validation import (
    StructuredSpecCurrentFactEvaluator,
)
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecReadService,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    ValidateStructuredSpec, build_structured_spec_validation_report,
)
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import (
    SectionDocumentContentProofAdapter,
)
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import (
    SectionEvidenceUseProofAdapter,
)
from plm_assistant.modules.solution.infrastructure.section_read_repository import (
    SqlAlchemySectionReadRepository,
)
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_read_repository import (
    SqlAlchemyStructuredSpecReadRepository,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)
from plm_assistant.modules.trace.application.create_link import (
    CreateTraceLinkRefs, TraceCreateError, TraceCreateService,
)
from plm_assistant.modules.trace.application.implements_coverage import (
    TraceImplementsCoverageService,
)
from plm_assistant.modules.trace.application.revoke_link import (
    RevokeTraceLink, TraceRevokeService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TracePublicEdgeResolver, TraceResourceVersionRef,
    TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef
from plm_assistant.modules.trace.infrastructure.create_repository import (
    SqlAlchemyTraceCreateRepository,
)
from plm_assistant.modules.trace.infrastructure.cycle_guard import (
    SqlAlchemyTraceCycleGuard,
)
from plm_assistant.modules.trace.infrastructure.implements_repository import (
    SqlAlchemyTraceImplementsRepository,
)
from plm_assistant.modules.trace.infrastructure.revoke_repository import (
    SqlAlchemyTraceRevokeRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_current_facts_for_trace",
    ROOT / "validation/sol-06-a13-p04-structured-spec-current-facts/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_trace(
    *, port, runtime, project, other_project, manager, token, member_token,
    csrf, first, second, repository, sources, draft, audit, license_guard,
    documents, downloads, parse_results, on_review=None,
    **_unused,
) -> None:
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    access = SqlAlchemyProjectReadAccess()
    requirement_owner = RequirementVersionTraceOwner(
        RequirementVersionReadService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyRequirementVersionReadRepository()))
    spec_owner = StructuredSpecTraceOwner(StructuredSpecReadService(
        unit_of_work=runtime.unit_of_work, access=access,
        license_guard=license_guard, authorization=authorization,
        specs=SqlAlchemyStructuredSpecReadRepository()))
    owners = TraceTargetProofService({
        ("requirement", "REQ-03"): requirement_owner,
        ("solution", "SOL-06"): spec_owner,
    })
    public = TracePublicEdgeResolver({
        "REQ-03": requirement_owner, "SOL-06": spec_owner,
    })
    coverage = TraceImplementsCoverageService(
        repository=SqlAlchemyTraceImplementsRepository(), owners=owners)
    creator = TraceCreateService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
        license_guard=license_guard, proofs=owners,
        cycle_guard=SqlAlchemyTraceCycleGuard(),
        repository=SqlAlchemyTraceCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        public_resolver=public)
    revoker = TraceRevokeService(
        unit_of_work=runtime.unit_of_work,
        sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
        license_guard=license_guard,
        repository=SqlAlchemyTraceRevokeRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)

    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results)
    evidence = EvidenceFixedProjectSourceService(
        sessions=access, projects=SqlAlchemyProjectAuthorizationRepository(),
        evidence=SqlAlchemyEvidenceFixedSourceRepository(), documents=fixed,
        allowed_project_roles=frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    evaluator = StructuredSpecCurrentFactEvaluator(
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(),
            fixed_sources=fixed),
        trace=coverage)
    validation_repository = SqlAlchemyStructuredSpecValidationRepository()
    command = ValidateStructuredSpec(
        token, b"c" * 32, uuid.uuid4(), project,
        second.structured_solution_spec_id, "structured-spec-trace-0001")

    def observe():
        with runtime.unit_of_work() as transaction:
            source = validation_repository.lock_source(
                transaction, project_id=project,
                spec_id=second.structured_solution_spec_id)
            assert source is not None
            observation = evaluator.evaluate(
                transaction, command=command, source=source)
            return build_structured_spec_validation_report(
                command, source.snapshot, observation,
                audit_event_id=uuid.uuid4(),
                observed_at=datetime.now(timezone.utc))

    requirement = draft.requirement_refs[0]
    source_ref = TraceResourceVersionRef(
        "REQ-03", requirement.requirement_id,
        requirement.requirement_version_id)

    missing = observe()
    assert missing.facts.trace == "FAIL" and not missing.ready_for_review

    old = creator.create_refs(CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project, source_ref,
        TraceResourceVersionRef(
            "SOL-06", first.spec_series_id,
            first.structured_solution_spec_id),
        "IMPLEMENTS"), idempotency_key="sol06-trace-old-0001")
    assert old.trace_link_id.int != 0
    assert observe().facts.trace == "FAIL"

    try:
        creator.create_refs(CreateTraceLinkRefs(
            token, csrf, uuid.uuid4(), other_project, source_ref,
            TraceResourceVersionRef(
                "SOL-06", second.spec_series_id,
                second.structured_solution_spec_id),
            "IMPLEMENTS"), idempotency_key="sol06-trace-cross-0001")
    except TraceCreateError as error:
        assert error.code in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND")
    else:
        raise AssertionError("cross-project SOL-06 Trace must fail closed")

    current = creator.create_refs(CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project, source_ref,
        TraceResourceVersionRef(
            "SOL-06", second.spec_series_id,
            second.structured_solution_spec_id),
        "IMPLEMENTS"), idempotency_key="sol06-trace-current-0001")
    ready = observe()
    assert ready.facts.trace == "PASS" and ready.valid
    assert ready.ready_for_review and ready.issue_codes == ()

    target = TraceVersionRef(
        "solution", "SOL-06", second.spec_series_id,
        second.structured_solution_spec_id, "PROJECT", project)
    requirement_ref = TraceVersionRef(
        "requirement", "REQ-03", requirement.requirement_id,
        requirement.requirement_version_id, "PROJECT", project)
    with runtime.unit_of_work() as transaction:
        proof = coverage.prove(
            transaction, query=TraceProofQuery(token, uuid.uuid4()),
            target=target, requirement_refs=(requirement_ref,))
        assert proof.trace_link_ids == (current.trace_link_id,)
        with psycopg.connect(
            host="127.0.0.1", port=port, user="poc_admin",
            dbname="postgres", autocommit=False,
        ) as competing:
            try:
                competing.execute(
                    "SELECT trace_link_id FROM plm.trc_links "
                    "WHERE trace_link_id=%s FOR UPDATE NOWAIT",
                    (current.trace_link_id,)).fetchone()
            except psycopg.errors.LockNotAvailable:
                competing.rollback()
            else:
                raise AssertionError("coverage must hold a shared Trace row lock")

    revoker.revoke(RevokeTraceLink(
        token, csrf, uuid.uuid4(), project, current.trace_link_id, 0),
        idempotency_key="sol06-trace-revoke-0001")
    assert observe().facts.trace == "FAIL"
    replacement = creator.create_refs(CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project, source_ref,
        TraceResourceVersionRef(
            "SOL-06", second.spec_series_id,
            second.structured_solution_spec_id),
        "IMPLEMENTS"), idempotency_key="sol06-trace-current-0002")
    assert replacement.trace_link_id != current.trace_link_id
    assert observe().ready_for_review

    if on_review is not None:
        on_review(
            port=port, runtime=runtime, project=project,
            other_project=other_project, manager=manager, token=token,
            member_token=member_token, csrf=csrf, first=first, second=second,
            repository=repository, sources=sources, draft=draft, audit=audit,
            license_guard=license_guard, documents=documents,
            downloads=downloads, parse_results=parse_results,
            evaluator=evaluator, validation_repository=validation_repository,
            trace_creator=creator,
        )

    print("SOL_06_A14_P03_TRACE_PG_PASS: fixed SOL-06 owner, exact current "
          "Requirement IMPLEMENTS set, old target/cross-project/revoke denial, "
          "active replacement and shared row lock")


def after_specs(*, created: dict[str, object], **specs) -> None:
    on_trace(
        **specs, csrf=created["csrf"], audit=created["audit"],
        license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"])


if __name__ == "__main__":
    prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created: prior.prior.on_created(
                **created, on_http=lambda **specs: after_specs(
                    created=created, **specs))))
