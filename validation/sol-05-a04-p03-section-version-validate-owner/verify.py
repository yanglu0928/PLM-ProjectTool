"""Disposable Windows PostgreSQL proof for the authorized VALIDATE Owner."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.prove_fixed_source import DocumentFixedSourceProofService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.reference_version_identity import SqlAlchemyReferenceVersionIdentity
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineRequirementUseProofService
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.solution.application.section_version_validation_contract import ValidateSectionVersion
from plm_assistant.modules.solution.application.validate_section_version import (
    SectionVersionCurrentValidator, SectionVersionValidationError,
    SectionVersionValidationService,
)
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import SectionDocumentContentProofAdapter
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import SectionEvidenceUseProofAdapter
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_validation_audit_source import SqlAlchemySectionVersionValidationAuditSource


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_create_fixture", ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _BrokenAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


def rejects(code: str, operation) -> None:
    try:
        operation()
    except SectionVersionValidationError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, scratch, locator, content, runtime, audit, license_guard,
               project, other_project, token, csrf, member_token, member_csrf,
               evidence, documents, downloads, parse_results, section, **_unused):
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s AND version_no=1", (section,)).fetchone()[0]
    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results)
    evidence_sources = EvidenceFixedProjectSourceService(
        sessions=SqlAlchemyProjectReadAccess(),
        projects=SqlAlchemyProjectAuthorizationRepository(),
        evidence=SqlAlchemyEvidenceFixedSourceRepository(), documents=fixed,
        allowed_project_roles=frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}))
    current = SectionVersionCurrentValidator(
        documents=SectionDocumentContentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed),
        requirements=OutlineRequirementUseProofService(
            approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
        evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence_sources))
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        sections=SqlAlchemySectionReadRepository(),
        versions=SqlAlchemySectionVersionReadRepository(), current=current,
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        audit_source=SqlAlchemySectionVersionValidationAuditSource())
    service = SectionVersionValidationService(**dependencies)
    command = ValidateSectionVersion(
        token, csrf, uuid.uuid4(), project, section, version, "v" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.validate(replace(
        command, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.validate(replace(
        command, project_id=other_project)))
    denied = SectionVersionValidationService(
        **{**dependencies, "license_guard": prior._DeniedLicense()})
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.validate(command))
    first = service.validate(command)
    assert first.facts.integrity == "PASS"
    assert first.facts.content == "PASS"
    assert first.facts.requirements == "PASS"
    assert first.facts.evidence == "PASS"
    assert first.facts.trace == first.facts.spec == "UNAVAILABLE"
    assert first.valid and not first.ready_for_review
    assert service.validate(replace(command, trace_id=uuid.uuid4())) == first
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SECTION_VERSION_VALIDATE'").fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_SECTION_VERSION_VALIDATED'").fetchone()[0] == 1
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',"
                   "lock_version=lock_version+1 WHERE evidence_id=%s", (evidence,))
    drift = service.validate(replace(command, idempotency_key="d" * 16))
    assert drift.facts.evidence == "UNAVAILABLE"
    assert not drift.valid and not drift.ready_for_review
    assert service.validate(command) == first
    broken = SectionVersionValidationService(
        **{**dependencies, "audit": _BrokenAudit()})
    rejects("SOLUTION_UNAVAILABLE", lambda: broken.validate(replace(
        command, idempotency_key="f" * 16)))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_SOL_SECTION_VERSION_VALIDATE'").fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='SOL_SECTION_VERSION_VALIDATED'").fetchone()[0] == 2
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                   "lock_version=lock_version+1 WHERE evidence_id=%s", (evidence,))
    print("SOL_05_A04_P03_VALIDATE_OWNER_PG_PASS: authorized source facts, "
          "UNAVAILABLE drift, first-result replay, receipt/audit atomicity")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_created))
