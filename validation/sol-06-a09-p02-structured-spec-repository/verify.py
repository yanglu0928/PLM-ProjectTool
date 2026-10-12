"""Windows 11 disposable PG18 repository proof for SOL-06 drafts."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
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
    "sol05_owner_for_sol06_repository", ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(*, port, runtime, project, other_project, manager, token,
               requirement, requirement_version, section, evidence,
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
        allowed_project_roles=frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    sources = StructuredSpecSourceProofService(
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed))
    repository = SqlAlchemyStructuredSpecCreateRepository()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        section_version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no DESC LIMIT 1",
            (section,)).fetchone()[0]
    draft = StructuredSpecDraftInput(
        project, None, None, "MIGRATION_SPEC", {
            "assumptions": ["合成来源待人工确认"], "exclusions": [],
            "source_system": "旧PLM", "target_system": "新PLM", "scope": "零件数据",
            "cleansing_rules": ["按料号去重"],
            "field_mappings": [{"source": "old_id", "target": "part_id"}],
            "trial_plan": "试点导入", "reconciliation_plan": "按料号对账",
            "rollback_plan": "恢复快照", "acceptance_criteria": "差异清零",
        },
        (SpecRequirementRef(requirement, requirement_version),),
        (SpecSectionRef(section, section_version),), (evidence,), ())

    def create(value: StructuredSpecDraftInput):
        with runtime.unit_of_work() as tx:
            proof = sources.prove(tx, session_token=token,
                                  trace_id=uuid.uuid4(), draft=value)
            result = repository.create(tx, version_id=uuid.uuid4(),
                                       actor_id=manager, proof=proof)
            tx.commit()
            return result

    first = create(draft)
    assert first.version_no == 1 and first.version_state == "DRAFT"
    assert first.spec_type == "MIGRATION_SPEC" and first.created_by == manager
    assert first.requirement_refs == draft.requirement_refs
    assert first.section_refs == draft.section_refs
    assert first.evidence_ids == draft.evidence_ids and first.artifact_ids == ()
    assert first.payload()["scope"] == "零件数据"
    with runtime.unit_of_work() as tx:
        replay = repository.first_result(
            tx, version_id=first.structured_solution_spec_id,
            project_id=project)
        assert replay == first
        assert repository.first_result(
            tx, version_id=first.structured_solution_spec_id,
            project_id=other_project) is None

    revised = replace(draft, spec_series_id=first.spec_series_id,
                      supersedes_version_ref=first.structured_solution_spec_id)
    second = create(revised)
    assert second.version_no == 2
    assert second.spec_series_id == first.spec_series_id
    assert second.supersedes_version_ref == first.structured_solution_spec_id
    try:
        create(revised)
    except RuntimeError as error:
        assert "series changed" in str(error), str(error)
    else:
        raise AssertionError("stale supersedes must be rejected")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_structured_specs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_payloads WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_requirement_refs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.sol_spec_section_refs WHERE spec_series_id=%s",
            (first.spec_series_id,)).fetchone()[0] == 2
    print("SOL_06_A09_P02_REPOSITORY_PG_PASS: real sources, first DRAFT, immutable "
          "reconstruction, same-series revision, stale predecessor/cross-project "
          "rejection, complete child rows; no public Owner/Audit/receipt")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_created))
