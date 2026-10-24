"""Win11 Edge/PG SOL-06 detail-to-revision acceptance on disposable data."""

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
    "sol06_detail_browser_for_revise",
    ROOT / "validation/sol-06-a10-p05-structured-spec-detail-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _seed_source_drift(*, port, runtime, project, manager, token, requirement,
                       requirement_version, section, evidence, documents, downloads,
                       parse_results, **_unused):
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
            "assumptions": ["synthetic historical source"], "exclusions": [],
            "source_system": "Legacy PLM", "target_system": "New PLM",
            "scope": "Historical parts", "cleansing_rules": ["Deduplicate"],
            "field_mappings": [{"source": "old_id", "target": "part_id"}],
            "trial_plan": "Historical trial", "reconciliation_plan": "Compare IDs",
            "rollback_plan": "Restore snapshot", "acceptance_criteria": "No differences",
        }, (SpecRequirementRef(requirement, requirement_version),),
        (SpecSectionRef(section, section_version),), (evidence,), ())
    repository = SqlAlchemyStructuredSpecCreateRepository()
    with runtime.unit_of_work() as transaction:
        proof = sources.prove(
            transaction, session_token=token, trace_id=uuid.uuid4(), draft=draft)
        stale = repository.create(
            transaction, version_id=uuid.uuid4(), actor_id=manager, proof=proof)
        transaction.commit()

    current_version, review, round_id = (uuid.uuid4() for _ in range(3))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.req_requirement_versions SET version_state='SUPERSEDED' "
                "WHERE requirement_version_id=%s", (requirement_version,))
            db.execute(
                "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
                "subject_id,policy_code,review_state,created_by) "
                "VALUES (%s,'PROJECT',%s,'REQUIREMENT_VERSION',%s,"
                "'REQUIREMENT_REVIEW','APPROVED',%s)",
                (review, project, requirement, manager))
            db.execute(
                "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,"
                "project_id,round_no,subject_version_id,round_state,started_by,started_at) "
                "VALUES (%s,%s,'PROJECT',%s,1,%s,'APPROVED',%s,statement_timestamp())",
                (round_id, review, project, current_version, manager))
            db.execute(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
                "requirement_id,project_id,version_no,statement,rationale,domain_name,"
                "priority,risk,requirement_classification,content_fingerprint,"
                "declared_source_count,declared_acceptance_count,declared_capability_count,"
                "declared_assumption_count,declared_exclusion_count,declared_dependency_count,"
                "declared_ai_task_count,version_state,review_ref,review_round_ref,created_by) "
                "VALUES (%s,%s,%s,2,'Synthetic current approved statement',"
                "'Synthetic source drift','PLM','HIGH','MEDIUM','PENDING_CONFIRMATION',"
                "%s,1,0,0,0,0,0,0,'APPROVED',%s,%s,%s)",
                (current_version, requirement, project, b"n" * 32,
                 review, round_id, manager))
            db.execute(
                "UPDATE plm.req_requirements SET current_approved_version_ref=%s "
                "WHERE requirement_id=%s", (current_version, requirement))
    return stale.structured_solution_spec_id, current_version


def on_browser(**browser) -> None:
    stale, current_requirement = _seed_source_drift(**browser)
    prior.prior.prior.on_browser(
        **browser, spec_mode=True, detail_mode=True, revise_mode=True,
        stale_spec=stale, current_requirement_version=current_requirement)


if __name__ == "__main__":
    prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **browser: on_browser(**browser)))
