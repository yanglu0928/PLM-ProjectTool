"""Win11 disposable PG18 proof for internal-only GLOBAL candidate scan."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.prove_reference_use_document import ReferenceUseDocumentProofService
from plm_assistant.modules.document.application.prove_reference_use_parse import ReferenceUseParseProofService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.reference_use_source import SqlAlchemyReferenceUseDocumentSource
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import ReferenceUseEvidenceProofService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_reference_solution import CreateReferenceSolution, ReferenceCreateService
from plm_assistant.modules.solution.application.list_global_reference_candidates import GlobalReferenceCandidateCatalog
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofService
from plm_assistant.modules.solution.application.set_global_reference_publication import GlobalReferencePublicationService, SetGlobalReferencePublication
from plm_assistant.modules.solution.application.set_reference_eligibility import ReferenceEligibilityService, SetReferenceEligibility
from plm_assistant.modules.solution.infrastructure.global_reference_candidate_repository import SqlAlchemyGlobalReferenceCandidateRepository
from plm_assistant.modules.solution.infrastructure.global_reference_publication_repository import SqlAlchemyGlobalReferencePublicationRepository
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import SqlAlchemyCurrentGlobalConfirmationRepository, SqlAlchemyCurrentReferenceUseRepository
from plm_assistant.modules.solution.infrastructure.reference_use_source import CurrentReferenceSourceAdapter


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_source_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_qualified(*, runtime, request, sources, audit, license_guard,
                 downloads, parse_results, **_unused) -> None:
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    creator = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository())
    unpublished = creator.create(
        CreateReferenceSolution(request, fixture.CSRF,
                                "Synthetic unreviewed first root",
                                "candidate-internal-unpublished-0001"))
    initial = creator.create(
            CreateReferenceSolution(request, fixture.CSRF,
                                    "Synthetic unreviewed raw name",
                                    "candidate-internal-create-0001"))
    ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository()).set(
            SetReferenceEligibility(
                fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
                initial.reference_solution_id, 0, "ELIGIBLE",
                "Synthetic human review", "candidate-internal-eligible-0001"))
    documents = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=downloads._storage)
    parses = ReferenceUseParseProofService(
        documents=documents, metadata=SqlAlchemyParseResultReadRepository(),
        storage=parse_results._storage)
    evidence = ReferenceUseEvidenceProofService(
        evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        documents=documents, parses=parses)
    catalog = GlobalReferenceCandidateCatalog(
        repository=SqlAlchemyGlobalReferenceCandidateRepository(),
        proof=ReferenceUseProofService(
            references=SqlAlchemyCurrentReferenceUseRepository(),
            sources=CurrentReferenceSourceAdapter(
                documents=documents, evidence=evidence),
            confirmations=SqlAlchemyCurrentGlobalConfirmationRepository()))
    project_id, trace_id = uuid.uuid4(), uuid.uuid4()

    def scan(*, after=None, limit=50):
        with runtime.unit_of_work() as tx:
            return catalog.scan(tx, trace_id=trace_id, project_id=project_id,
                                after_reference_solution_id=after, limit=limit)

    assert scan().items == ()
    assert unpublished.reference_solution_id < initial.reference_solution_id
    owner = GlobalReferencePublicationService(
        unit_of_work=runtime.unit_of_work,
        admin=SqlAlchemyLicenseImportAccess(), license_guard=license_guard,
        sources=sources,
        repository=SqlAlchemyGlobalReferencePublicationRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    owner.set(SetGlobalReferencePublication(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(),
        initial.reference_solution_id, initial.reference_version_id,
        0, "PUBLISH", "审定的合成标签", "仅供项目候选",
        "candidate-internal-publish-0001"))
    page = scan()
    assert len(page.items) == 1 and not page.has_more
    item = page.items[0]
    assert item.reference_solution_id == initial.reference_solution_id
    assert item.reference_version_id == initial.reference_version_id
    assert item.display_label == "审定的合成标签"
    assert not hasattr(item, "name") and not hasattr(item, "source_fingerprint")
    first = scan(limit=1)
    assert first.items == () and first.has_more
    assert first.next_after_reference_solution_id == unpublished.reference_solution_id
    second = scan(after=first.next_after_reference_solution_id, limit=1)
    assert second.items == (item,) and not second.has_more
    ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository()).set(
            SetReferenceEligibility(
                fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
                initial.reference_solution_id, 1, "RESTRICTED",
                "Current qualification withdrawn", "candidate-internal-restrict-0001"))
    assert scan().items == ()
    owner.set(SetGlobalReferencePublication(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(),
        initial.reference_solution_id, initial.reference_version_id,
        1, "REVOKE", None, "管理员撤回", "candidate-internal-revoke-0001"))
    assert scan().items == ()


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
    print("SOL_03_A04_P03_P03_P06_A03_P05_A02_GLOBAL_CANDIDATE_INTERNAL_PG_PASS")
