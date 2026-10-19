"""Win11 disposable PG proof for SOL-06 current fact evaluation."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
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
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_repository_for_current_facts",
    ROOT / "validation/sol-06-a09-p02-structured-spec-repository/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_current_facts(*, runtime, project, token, first, second,
                     documents, downloads, parse_results, **_unused) -> None:
    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results)
    evidence_sources = EvidenceFixedProjectSourceService(
        sessions=SqlAlchemyProjectReadAccess(),
        projects=SqlAlchemyProjectAuthorizationRepository(),
        evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        documents=fixed,
        allowed_project_roles=frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    evaluator = StructuredSpecCurrentFactEvaluator(
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed))
    repository = SqlAlchemyStructuredSpecValidationRepository()

    with runtime.unit_of_work() as transaction:
        current_source = repository.lock_source(
            transaction, project_id=project,
            spec_id=second.structured_solution_spec_id)
        historical_source = repository.lock_source(
            transaction, project_id=project,
            spec_id=first.structured_solution_spec_id)
        assert current_source is not None and historical_source is not None
        current_command = ValidateStructuredSpec(
            token, b"c" * 32, uuid.uuid4(), project,
            second.structured_solution_spec_id,
            "structured-spec-current-facts-0001")
        historical_command = ValidateStructuredSpec(
            token, b"c" * 32, uuid.uuid4(), project,
            first.structured_solution_spec_id,
            "structured-spec-current-facts-0002")
        current = evaluator.evaluate(
            transaction, command=current_command, source=current_source)
        historical = evaluator.evaluate(
            transaction, command=historical_command, source=historical_source)
        assert all(getattr(current.facts, name) == "PASS" for name in (
            "integrity", "payload", "requirements", "sections", "evidence",
            "artifacts", "current_version"))
        assert current.facts.trace == "UNAVAILABLE"
        assert historical.facts.current_version == "FAIL"
        assert all(getattr(historical.facts, name) == "PASS" for name in (
            "integrity", "payload", "requirements", "sections", "evidence",
            "artifacts"))
        statuses = {item.code: item.status for item in current.type_checks.checks}
        assert statuses == {
            "SCOPE_MAPPING": "PASS",
            "TRIAL_PLAN": "PASS",
            "RECONCILIATION_PLAN": "PASS",
            "ROLLBACK_PLAN": "PASS",
            "ACCEPTANCE_CRITERIA": "PASS",
        }
        report = build_structured_spec_validation_report(
            current_command, current_source.snapshot, current,
            audit_event_id=uuid.uuid4(),
            observed_at=datetime.now(timezone.utc))
        assert report.valid and not report.ready_for_review
        assert "TRACE_COVERAGE_UNAVAILABLE" in report.issue_codes
        assert report.issue_codes == ("TRACE_COVERAGE_UNAVAILABLE",)

    print("SOL_06_A13_P04_CURRENT_FACTS_PG_PASS: current Owner facts, historical "
          "identity FAIL, V2 design declarations PASS, missing Trace "
          "UNAVAILABLE, valid does not become ready")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **created: prior.on_created(
            **created, on_http=lambda **specs: on_current_facts(
                **specs, documents=created["documents"],
                downloads=created["downloads"],
                parse_results=created["parse_results"]))))
