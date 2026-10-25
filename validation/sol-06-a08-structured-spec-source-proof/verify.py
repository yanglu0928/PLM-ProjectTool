"""Windows 11 disposable PG18 composition proof for SOL-06 fixed sources."""

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
from plm_assistant.modules.solution.application.prove_structured_spec_sources import (
    StructuredSpecSourceError, StructuredSpecSourceProofService,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
)
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import SectionDocumentContentProofAdapter
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import SectionEvidenceUseProofAdapter
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol05_source_owner_fixture", ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def rejects(expected: str, action) -> None:
    try:
        action()
    except StructuredSpecSourceError as error:
        assert error.code == expected, (expected, error.code)
    else:
        raise AssertionError("expected " + expected)


def on_created(*, port, scratch, locator, content, runtime, project,
               other_project, token, evidence, document_version, documents,
               downloads, parse_results, section, requirement,
               requirement_version, **_unused) -> None:
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
    service = StructuredSpecSourceProofService(
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        latest, old = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no DESC",
            (section,)).fetchall()[0][0], db.execute(
                "SELECT solution_section_version_id FROM plm.sol_section_versions "
                "WHERE solution_section_id=%s AND version_no=1", (section,)).fetchone()[0]
    payload = {
        "assumptions": ["合成来源待人工确认"], "exclusions": [],
        "source_system": "旧PLM", "target_system": "新PLM", "scope": "零件数据",
        "cleansing_rules": ["按料号去重"],
        "field_mappings": [{"source": "old_id", "target": "part_id"}],
        "trial_plan": "试点导入", "reconciliation_plan": "按料号对账",
        "rollback_plan": "恢复快照", "acceptance_criteria": "差异清零",
    }
    draft = StructuredSpecDraftInput(
        project, None, None, "MIGRATION_SPEC", payload,
        (SpecRequirementRef(requirement, requirement_version),),
        (SpecSectionRef(section, latest),), (evidence,), ())

    def prove(value: StructuredSpecDraftInput = draft):
        with runtime.unit_of_work() as tx:
            return service.prove(tx, session_token=token,
                                 trace_id=uuid.uuid4(), draft=value)

    proof = prove()
    assert proof.sections[0].solution_section_version_id == latest
    assert proof.requirements[0].requirement_version_id == requirement_version
    assert proof.evidence[0].evidence_id == evidence
    assert len(proof.content_fingerprint) == 32

    from dataclasses import replace
    rejects("SOURCE_UNAVAILABLE", lambda: prove(replace(
        draft, artifact_ids=(uuid.uuid4(),))))
    rejects("SOURCE_UNAVAILABLE", lambda: prove(replace(
        draft, project_id=other_project)))
    rejects("SOURCE_UNAVAILABLE", lambda: prove(replace(
        draft, section_refs=(SpecSectionRef(section, old),))))

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',"
                   "lock_version=lock_version+1 WHERE evidence_id=%s", (evidence,))
        rejects("SOURCE_UNAVAILABLE", prove)
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                   "lock_version=lock_version+1 WHERE evidence_id=%s", (evidence,))
    source_path = scratch / "private-documents" / locator
    source_path.write_bytes(b"X" * len(content))
    rejects("SOURCE_UNAVAILABLE", prove)
    source_path.write_bytes(content)
    assert prove().content_fingerprint != proof.content_fingerprint  # evidence lock changed
    print("SOL_06_A08_SOURCE_PROOF_PG_PASS: current approved requirement, latest "
          "fixed section, physical document, eligible evidence, cross-project/"
          "stale/artifact/invalidation/tamper rejection")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_created))
