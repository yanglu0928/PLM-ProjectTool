"""Win11 disposable PostgreSQL proof for the authorized SOL-06 validator."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg

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
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
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
from plm_assistant.modules.solution.application.evaluate_structured_spec_validation import (
    StructuredSpecCurrentFactEvaluator,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    ValidateStructuredSpec,
)
from plm_assistant.modules.solution.application.validate_structured_spec import (
    StructuredSpecValidationError, StructuredSpecValidationService,
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
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_audit_source import (
    SqlAlchemyStructuredSpecValidationAuditSource,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_current_facts_for_validation_service",
    ROOT / "validation/sol-06-a13-p04-structured-spec-current-facts/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _DeniedLicense:
    def require_valid(self, **_kwargs):
        raise RuntimeLicenseError("EXPIRED")


class _BrokenAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


def rejects(code: str, operation) -> None:
    try:
        operation()
    except StructuredSpecValidationError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_validation_service(
    *, port, runtime, project, other_project, token, member_token,
    csrf, member_csrf, second, first, audit, license_guard, evidence,
    documents, downloads, parse_results, **_unused,
) -> None:
    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results)
    evidence_sources = EvidenceFixedProjectSourceService(
        sessions=SqlAlchemyProjectReadAccess(),
        projects=SqlAlchemyProjectAuthorizationRepository(),
        evidence=SqlAlchemyEvidenceFixedSourceRepository(), documents=fixed,
        allowed_project_roles=frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    evaluator = StructuredSpecCurrentFactEvaluator(
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(),
            fixed_sources=fixed),
        trace=prior.UnavailableTraceCoverage())
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyStructuredSpecValidationRepository(),
        evaluator=evaluator, receipts=SqlAlchemyIdempotencyReceipts(),
        audit=audit,
        audit_source=SqlAlchemyStructuredSpecValidationAuditSource())
    service = StructuredSpecValidationService(**dependencies)
    command = ValidateStructuredSpec(
        token, csrf, uuid.uuid4(), project,
        second.structured_solution_spec_id,
        "structured-spec-service-0001")

    rejects("AUTH_ACCESS_DENIED", lambda: service.validate(replace(
        command, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.validate(replace(
        command, project_id=other_project)))
    denied = StructuredSpecValidationService(
        **{**dependencies, "license_guard": _DeniedLicense()})
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.validate(command))

    first_report = service.validate(command)
    assert first_report.valid and not first_report.ready_for_review
    assert first_report.facts.integrity == "PASS"
    assert first_report.facts.current_version == "PASS"
    assert first_report.facts.trace == "UNAVAILABLE"
    assert service.validate(replace(
        command, trace_id=uuid.uuid4())) == first_report
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as database:
        assert database.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_STRUCTURED_SPEC_VALIDATE'"
        ).fetchone()[0] == 1
        assert database.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_STRUCTURED_SPEC_VALIDATED'"
        ).fetchone()[0] == 1
        database.execute(
            "UPDATE plm.evd_evidence_records "
            "SET eligibility_state='INELIGIBLE', lock_version=lock_version+1 "
            "WHERE evidence_id=%s", (evidence,))

    drift = service.validate(replace(
        command, idempotency_key="structured-spec-service-0002"))
    assert drift.facts.evidence == "UNAVAILABLE"
    assert drift.facts.integrity == "UNAVAILABLE"
    assert not drift.valid and not drift.ready_for_review
    assert service.validate(command) == first_report
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as database:
        database.execute(
            "UPDATE plm.evd_evidence_records "
            "SET eligibility_state='ELIGIBLE', lock_version=lock_version+1 "
            "WHERE evidence_id=%s", (evidence,))

    member = service.validate(ValidateStructuredSpec(
        member_token, member_csrf, uuid.uuid4(), project,
        second.structured_solution_spec_id,
        "structured-spec-service-0003"))
    assert member.facts.evidence == "PASS"
    assert member.facts.integrity == "FAIL"
    assert not member.valid and not member.ready_for_review
    historical = service.validate(ValidateStructuredSpec(
        token, csrf, uuid.uuid4(), project,
        first.structured_solution_spec_id,
        "structured-spec-service-0004"))
    assert historical.facts.integrity == "FAIL"
    assert not historical.valid and not historical.ready_for_review
    assert historical.facts.current_version == "FAIL"

    broken = StructuredSpecValidationService(
        **{**dependencies, "audit": _BrokenAudit()})
    rejects("SOLUTION_UNAVAILABLE", lambda: broken.validate(replace(
        command, idempotency_key="structured-spec-service-0005")))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as database:
        assert database.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_STRUCTURED_SPEC_VALIDATE'"
        ).fetchone()[0] == 4
        assert database.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_STRUCTURED_SPEC_VALIDATED'"
        ).fetchone()[0] == 4
    print("SOL_06_A13_P05_VALIDATION_SERVICE_PG_PASS: manager/member authorization, "
          "current and historical first observations, durable exact replay, "
          "source drift resampling, License/CSRF/isolation and Audit rollback")


def after_specs(*, created: dict[str, object], **specs) -> None:
    shared = dict(
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"])
    prior.on_current_facts(**specs, **shared)
    on_validation_service(
        **specs, **shared, csrf=created["csrf"],
        member_csrf=created["member_csrf"], audit=created["audit"],
        license_guard=created["license_guard"], evidence=created["evidence"])


if __name__ == "__main__":
    prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created: prior.prior.on_created(
                **created, on_http=lambda **specs: after_specs(
                    created=created, **specs))))
