"""Disposable real Auth/Document/Evidence/PG proof for SectionVersion Owner.

The Requirement reference set is empty in this slice; a nonempty approved
Requirement integration remains a separate P11 acceptance condition.
"""

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
from plm_assistant.modules.solution.application.create_section_version import (
    CreateSectionVersion, SectionVersionCreateError, SectionVersionCreateService,
)
from plm_assistant.modules.solution.application.prove_section_version_input import SectionVersionInputProofService
from plm_assistant.modules.solution.application.section_version_input import SectionRequirementRef, SectionVersionDraftInput
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import SectionDocumentContentProofAdapter
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import SectionEvidenceUseProofAdapter
from plm_assistant.modules.solution.infrastructure.section_version_base import SqlAlchemyCurrentSectionVersionBase
from plm_assistant.modules.solution.infrastructure.section_version_create_repository import SqlAlchemySectionVersionCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_source_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _BrokenAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


class _DeniedLicense:
    def require_valid(self, *, trace_id):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def rejects(code: str, operation) -> None:
    try:
        operation()
    except SectionVersionCreateError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, scratch, locator, content, runtime, audit, license_guard,
               project, other_project, token, csrf, member_token, member_csrf,
               manager, evidence, document_version, documents, downloads,
               parse_results, on_http=None, **_unused):
    outline, section = uuid.uuid4(), uuid.uuid4()
    requirement, requirement_version, review, round_id = (
        uuid.uuid4() for _ in range(4))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            # Only parent identities use the fixture's controlled seed bypass.
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,"
                "created_by) VALUES (%s,%s,'Section version parent',%s)",
                (outline, project, manager))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'body',%s)",
                (section, outline, project, manager))
            # Synthetic, internally consistent approved Requirement fixture;
            # this is not a customer Review ceremony or business approval.
            db.execute(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                "requirement_code,requirement_code_normalized,created_by) "
                "VALUES (%s,%s,'SOL-SECTION-REQ','SOL-SECTION-REQ',%s)",
                (requirement, project, manager))
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
                (round_id, review, project, requirement_version, manager))
            db.execute(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
                "requirement_id,project_id,version_no,statement,rationale,domain_name,"
                "priority,risk,requirement_classification,content_fingerprint,"
                "declared_source_count,declared_acceptance_count,"
                "declared_capability_count,declared_assumption_count,"
                "declared_exclusion_count,declared_dependency_count,"
                "declared_ai_task_count,version_state,review_ref,review_round_ref,"
                "created_by) VALUES (%s,%s,%s,1,'Synthetic approved statement',"
                "'Synthetic reason','PLM','HIGH','MEDIUM','PENDING_CONFIRMATION',"
                "%s,1,0,0,0,0,0,0,'APPROVED',%s,%s,%s)",
                (requirement_version, requirement, project, b"r" * 32,
                 review, round_id, manager))
            db.execute(
                "UPDATE plm.req_requirements SET current_approved_version_ref=%s "
                "WHERE requirement_id=%s",
                (requirement_version, requirement))

    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results,
    )
    evidence_sources = EvidenceFixedProjectSourceService(
        sessions=SqlAlchemyProjectReadAccess(),
        projects=SqlAlchemyProjectAuthorizationRepository(),
        evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        documents=fixed,
        allowed_project_roles=frozenset({
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
    )
    inputs = SectionVersionInputProofService(
        bases=SqlAlchemyCurrentSectionVersionBase(),
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources),
    )
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        inputs=inputs,
        repository=SqlAlchemySectionVersionCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(),
    )
    service = SectionVersionCreateService(**dependencies, audit=audit)
    draft = SectionVersionDraftInput(
        project, section, "Implementation body", document_version, None,
        (SectionRequirementRef(requirement, requirement_version),),
        (evidence,), ({"note": "synthetic proof"},), ())
    cmd = CreateSectionVersion(token, csrf, uuid.uuid4(), draft, "v" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.create(replace(
        cmd, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, draft=replace(draft, project_id=other_project))))
    denied = SectionVersionCreateService(
        **{**dependencies, "license_guard": _DeniedLicense()}, audit=audit)
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    rejects("SOURCE_UNAVAILABLE", lambda: service.create(replace(
        cmd, draft=replace(draft, content_document_version_ref=None,
                           content_artifact_ref=uuid.uuid4()),
        idempotency_key="a" * 16)))
    first = service.create(cmd)
    assert first.version_no == 1 and first.version_state == "DRAFT"
    assert first.evidence_ids == (evidence,)
    assert first.requirement_refs == draft.requirement_refs
    assert service.create(replace(cmd, trace_id=uuid.uuid4())) == first
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',"
                   "lock_version=lock_version+1 WHERE evidence_id=%s", (evidence,))
        rejects("SOURCE_UNAVAILABLE", lambda: service.create(replace(
            cmd, idempotency_key="e" * 16)))
        assert service.create(cmd) == first
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                   "lock_version=lock_version+1 WHERE evidence_id=%s", (evidence,))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.req_requirements SET current_approved_version_ref=NULL "
                       "WHERE requirement_id=%s", (requirement,))
        rejects("SOURCE_UNAVAILABLE", lambda: service.create(replace(
            cmd, idempotency_key="r" * 16)))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.req_requirements SET current_approved_version_ref=%s "
                       "WHERE requirement_id=%s", (requirement_version, requirement))
    source_path = scratch / "private-documents" / locator
    source_path.write_bytes(b"X" * len(content))
    rejects("SOURCE_UNAVAILABLE", lambda: service.create(replace(
        cmd, idempotency_key="d" * 16)))
    assert service.create(cmd) == first
    source_path.write_bytes(content)
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(
        cmd, draft=replace(draft, title="Changed"))))
    member = service.create(CreateSectionVersion(
        member_token, member_csrf, uuid.uuid4(), draft, "m" * 16))
    assert member.version_no == 2
    assert member.supersedes_version_ref == first.solution_section_version_id
    broken = SectionVersionCreateService(**dependencies, audit=_BrokenAudit())
    rejects("SOLUTION_UNAVAILABLE", lambda: broken.create(replace(
        cmd, idempotency_key="f" * 16)))
    parallel = replace(cmd, idempotency_key="p" * 16)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.create, (parallel, parallel)))
    assert results[0] == results[1] and results[0].version_no == 3
    different = (replace(cmd, idempotency_key="q" * 16),
                 replace(cmd, idempotency_key="z" * 16))
    with ThreadPoolExecutor(max_workers=2) as pool:
        different_results = tuple(pool.map(service.create, different))
    assert {item.version_no for item in different_results} == {4, 5}
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.sol_section_evidence_refs "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.sol_section_requirement_refs "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.sol_section_version_create_results "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                          "WHERE operation='V1_SOL_SECTION_VERSION_CREATE'").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_SECTION_VERSION_CREATED'").fetchone()[0] == 5
    if on_http is not None:
        on_http(port=port, scratch=scratch, locator=locator, content=content,
                runtime=runtime, audit=audit, license_guard=license_guard,
                project=project, other_project=other_project, token=token,
                csrf=csrf, member_token=member_token, member_csrf=member_csrf,
                manager=manager, evidence=evidence,
                document_version=document_version, documents=documents,
                downloads=downloads, parse_results=parse_results,
                outline=outline, section=section,
                requirement=requirement,
                requirement_version=requirement_version)
    print("SOL_05_A02_P11_SOURCE_OWNER_PG_PASS: real Auth/Project/"
          "Document/Requirement/Evidence/PG18, source invalidation, replay, "
          "same/different parallel keys, next version, rollback, "
          "one receipt and audit per create")
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
