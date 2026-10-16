"""Win11 Edge/PG SOL-06 project list, pagination and detail acceptance."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.document.application.prove_fixed_source import DocumentFixedSourceProofService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.reference_version_identity import SqlAlchemyReferenceVersionIdentity
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineRequirementUseProofService
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.solution.application.prove_structured_spec_sources import StructuredSpecSourceProofService
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
)
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import SectionDocumentContentProofAdapter
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import SectionEvidenceUseProofAdapter
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.solution.infrastructure.structured_spec_create_repository import SqlAlchemyStructuredSpecCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_detail_browser_for_list",
    ROOT / "validation/sol-06-a10-p05-structured-spec-detail-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _seed_history(*, port, runtime, project, manager, token, requirement,
                  requirement_version, section, evidence, documents, downloads,
                  parse_results, **_unused) -> None:
    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results)
    evidence_sources = EvidenceFixedProjectSourceService(
        sessions=SqlAlchemyProjectReadAccess(),
        projects=SqlAlchemyProjectAuthorizationRepository(),
        evidence=SqlAlchemyEvidenceFixedSourceRepository(), documents=fixed,
        allowed_project_roles=frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    sources = StructuredSpecSourceProofService(
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        section_version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no DESC LIMIT 1",
            (section,)).fetchone()[0]
    draft = StructuredSpecDraftInput(
        project, None, None, "MIGRATION_SPEC", {
            "assumptions": ["synthetic list fixture"], "exclusions": [],
            "source_system": "Old PLM", "target_system": "New PLM",
            "scope": "Parts", "cleansing_rules": ["Deduplicate"],
            "field_mappings": [{"source": "old_id", "target": "part_id"}],
            "trial_plan": "Trial batch", "reconciliation_plan": "Compare by part number",
            "rollback_plan": "Restore snapshot", "acceptance_criteria": "No differences",
        }, (SpecRequirementRef(requirement, requirement_version),),
        (SpecSectionRef(section, section_version),), (evidence,), ())
    repository = SqlAlchemyStructuredSpecCreateRepository()
    with runtime.unit_of_work() as transaction:
        proof = sources.prove(
            transaction, session_token=token, trace_id=uuid.uuid4(), draft=draft)
        for _ in range(50):
            repository.create(
                transaction, version_id=uuid.uuid4(), actor_id=manager, proof=proof)
        transaction.commit()


def on_browser(**browser) -> None:
    _seed_history(**browser)
    prior.prior.prior.on_browser(
        **browser, spec_mode=True, detail_mode=True, list_mode=True)


if __name__ == "__main__":
    prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **browser: on_browser(**browser)))
