"""Disposable Windows 11 PG18 SOL-06 authorized atomic create acceptance."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.prove_fixed_source import DocumentFixedSourceProofService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.reference_version_identity import SqlAlchemyReferenceVersionIdentity
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineRequirementUseProofService
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.solution.application.create_structured_spec import (
    CreateStructuredSpec, StructuredSpecCreateError, StructuredSpecCreateService,
)
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
    "sol05_owner_for_sol06_create",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def rejects(code, operation):
    try:
        operation()
    except StructuredSpecCreateError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager, token, csrf, member_token, member_csrf, requirement,
               requirement_version, section, evidence, documents, downloads,
               parse_results, **_unused):
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
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        sources=sources,
        repository=SqlAlchemyStructuredSpecCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts())
    service = StructuredSpecCreateService(**dependencies, audit=audit)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        section_version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s ORDER BY version_no DESC LIMIT 1",
            (section,)).fetchone()[0]
    draft = StructuredSpecDraftInput(
        project, None, None, "MIGRATION_SPEC", {
            "assumptions": ["synthetic pending confirmation"], "exclusions": [],
            "source_system": "old", "target_system": "new", "scope": "parts",
            "cleansing_rules": ["deduplicate"],
            "field_mappings": [{"source": "old_id", "target": "part_id"}],
            "trial_plan": "trial", "reconciliation_plan": "reconcile",
            "rollback_plan": "snapshot", "acceptance_criteria": "zero difference",
        }, (SpecRequirementRef(requirement, requirement_version),),
        (SpecSectionRef(section, section_version),), (evidence,), ())
    cmd = CreateStructuredSpec(token, csrf, uuid.uuid4(), draft, "s" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.create(replace(
        cmd, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, draft=replace(draft, project_id=other_project))))
    denied = StructuredSpecCreateService(
        **{**dependencies, "license_guard": prior._DeniedLicense()}, audit=audit)
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    rejects("SOURCE_UNAVAILABLE", lambda: service.create(replace(
        cmd, draft=replace(draft, artifact_ids=(uuid.uuid4(),)),
        idempotency_key="a" * 16)))
    first = service.create(cmd)
    assert first.version_state == "DRAFT" and first.version_no == 1
    assert service.create(replace(cmd, trace_id=uuid.uuid4())) == first
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(
        cmd, draft=replace(draft, payload={**draft.payload, "scope": "changed"}))))
    broken = StructuredSpecCreateService(
        **dependencies, audit=prior._BrokenAudit())
    rejects("SOLUTION_UNAVAILABLE", lambda: broken.create(replace(
        cmd, idempotency_key="f" * 16)))
    parallel = replace(cmd, idempotency_key="p" * 16)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.create, (parallel, parallel)))
    assert results[0] == results[1]
    member = service.create(CreateStructuredSpec(
        member_token, member_csrf, uuid.uuid4(), draft, "m" * 16))
    assert member.created_by != manager
    revised = replace(draft, spec_series_id=first.spec_series_id,
                      supersedes_version_ref=first.structured_solution_spec_id)
    second = service.create(replace(cmd, draft=revised, idempotency_key="v" * 16))
    assert second.version_no == 2 and second.spec_series_id == first.spec_series_id
    rejects("SOLUTION_UNAVAILABLE", lambda: service.create(replace(
        cmd, draft=revised, idempotency_key="w" * 16)))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_structured_specs").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                          "WHERE operation='V1_SOL_STRUCTURED_SPEC_CREATE'").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_STRUCTURED_SPEC_CREATED'").fetchone()[0] == 4
    print("SOL_06_A09_P03_CREATE_PG_PASS: real auth, project roles, current sources, "
          "license, exact/concurrent replay, revision, audit rollback")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_created))
