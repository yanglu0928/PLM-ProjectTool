"""Disposable Win11/PG18 same-transaction Section Review readiness proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from plm_assistant.entrypoints import windows_solution_outline as win
from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.solution.application.section_review_readiness import (
    SectionReviewReadinessError, SectionReviewReadinessService,
)
from plm_assistant.modules.solution.application.section_version_validation_contract import SectionCurrentFactQuery
from plm_assistant.modules.solution.infrastructure.section_review_readiness_repository import (
    SqlAlchemySectionReviewReadinessRepository,
)
from plm_assistant.modules.trace.application.implements_coverage import TraceImplementsCoverageService
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.implements_repository import SqlAlchemyTraceImplementsRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_review_readiness_prior",
    ROOT / "validation/sol-05-a04-p12-p05-p04-section-review-readiness-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _observe(*, phase, runtime, project, section, version, token,
             documents, downloads, parse_results, license_guard):
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    access = win.SqlAlchemyProjectReadAccess()
    requirement_owner = RequirementVersionTraceOwner(RequirementVersionReadService(
        unit_of_work=runtime.unit_of_work, access=access,
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyRequirementVersionReadRepository()))
    section_owner = SectionVersionTraceOwner(win.SectionVersionReadService(
        unit_of_work=runtime.unit_of_work, access=access,
        license_guard=license_guard, authorization=authorization,
        sections=win.SqlAlchemySectionReadRepository(),
        versions=win.SqlAlchemySectionVersionReadRepository()))
    trace = TraceImplementsCoverageService(
        repository=SqlAlchemyTraceImplementsRepository(),
        owners=TraceTargetProofService({
            ("requirement", "REQ-03"): requirement_owner,
            ("solution", "SOL-05"): section_owner,
        }))
    fixed = win.DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=win.SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results)
    evidence = win.EvidenceFixedProjectSourceService(
        sessions=win.SqlAlchemyProjectReadAccess(),
        projects=win.SqlAlchemyProjectAuthorizationRepository(),
        evidence=win.SqlAlchemyEvidenceFixedSourceRepository(),
        documents=fixed,
        allowed_project_roles=frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    current = win.SectionVersionCurrentValidator(
        documents=win.SectionDocumentContentProofAdapter(
            identities=win.SqlAlchemyReferenceVersionIdentity(),
            fixed_sources=fixed),
        requirements=win.OutlineRequirementUseProofService(
            approved_versions=win.SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        evidence=win.SectionEvidenceUseProofAdapter(fixed_sources=evidence),
        trace=trace,
        specs=win.SectionCurrentSpecQualificationService(
            win.SectionStructuredSpecQualificationService(
                specs=win.SqlAlchemySectionSpecCandidateRepository(),
                sections=win.SqlAlchemySectionSpecSourceRepository(),
                reviews=win.SqlAlchemyReviewSnapshotReadRepository())),
    )
    readiness = SectionReviewReadinessService(
        repository=SqlAlchemySectionReviewReadinessRepository(),
        current=current)
    query = SectionCurrentFactQuery(
        token, uuid.uuid4(), project, section, version)
    with runtime.unit_of_work() as tx:
        if phase == "ready":
            proof = readiness.prove(tx, query=query)
            assert proof.version.solution_section_version_id == version
            assert {getattr(proof.facts, name) for name in (
                "integrity", "content", "requirements", "evidence", "trace", "spec"
            )} == {"PASS"}
        else:
            try:
                readiness.prove(tx, query=query)
            except SectionReviewReadinessError:
                pass
            else:
                raise AssertionError("revoked current Trace cannot submit Review")


if __name__ == "__main__":
    prior._observation_hook = _observe
    fixture = prior.fixture
    fixture._after_submit = prior._after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
    print("SOL_05_A04_P13_P02_SECTION_CURRENT_REVIEW_READINESS_WINDOWS_PASS")
