"""Disposable Win11 PG/real-file Reference use composition verification."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import psycopg

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
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofError, ReferenceUseProofService, ReferenceUseQuery
from plm_assistant.modules.solution.application.set_reference_eligibility import ReferenceEligibilityService, SetReferenceEligibility
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import SqlAlchemyCurrentGlobalConfirmationRepository, SqlAlchemyCurrentReferenceUseRepository
from plm_assistant.modules.solution.infrastructure.reference_use_source import CurrentReferenceSourceAdapter


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


project_fixture = module(
    "project_use_composition_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
global_fixture = module(
    "global_use_composition_fixture",
    "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")


def services(*, runtime, sources, audit, license_guard, downloads, parse_results):
    documents = ReferenceUseDocumentProofService(
        sources=SqlAlchemyReferenceUseDocumentSource(),
        storage=downloads._storage)
    parses = ReferenceUseParseProofService(
        documents=documents, metadata=SqlAlchemyParseResultReadRepository(),
        storage=parse_results._storage)
    evidence = ReferenceUseEvidenceProofService(
        evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        documents=documents, parses=parses)
    reference = ReferenceUseProofService(
        references=SqlAlchemyCurrentReferenceUseRepository(),
        sources=CurrentReferenceSourceAdapter(
            documents=documents, evidence=evidence),
        confirmations=SqlAlchemyCurrentGlobalConfirmationRepository())
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    eligibility = ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository())
    return reference, eligibility, common


def denied(action):
    try:
        action()
    except ReferenceUseProofError:
        return
    raise AssertionError("stale or unavailable Reference accepted")


def project_created(*, runtime, sources, audit, license_guard,
                    created, project, other_project, token, csrf,
                    downloads, parse_results, scratch, locator, content, port,
                    **_unused):
    proof, eligibility, _ = services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 0, "ELIGIBLE", "Source reviewed",
        "composition-project-eligible-0001"))
    query = ReferenceUseQuery(
        uuid.uuid4(), project, created.reference_solution_id,
        created.reference_version_id, "PROJECT")
    with runtime.unit_of_work() as tx:
        assert proof.prove(tx, query).reference_version_id == created.reference_version_id
        denied(lambda: proof.prove(
            tx, replace(query, target_project_id=other_project)))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            try:
                db.execute(
                    "SELECT reference_solution_id FROM plm.sol_reference_solutions "
                    "WHERE reference_solution_id=%s FOR UPDATE NOWAIT",
                    (created.reference_solution_id,))
            except psycopg.errors.LockNotAvailable:
                pass
            else:
                raise AssertionError("current proof did not retain Reference root lock")
    file = scratch / "private-documents" / locator
    original = file.read_bytes()
    try:
        file.write_bytes(b"X" * len(content))
        with runtime.unit_of_work() as tx:
            denied(lambda: proof.prove(tx, query))
    finally:
        file.write_bytes(original)
    eligibility.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 1, "RESTRICTED", "No longer approved",
        "composition-project-restrict-0002"))
    with runtime.unit_of_work() as tx:
        denied(lambda: proof.prove(tx, query))
    return 0


def global_qualified(*, runtime, request, sources, audit, license_guard,
                     downloads, parse_results, qualified, confirmed, **_unused):
    proof, eligibility, common = services(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard, downloads=downloads,
        parse_results=parse_results)
    created = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(request, global_fixture.CSRF,
                                    "Global outline source",
                                    "composition-global-create-0001"))
    eligibility.set(SetReferenceEligibility(
        global_fixture.TOKEN, global_fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
        created.reference_solution_id, 0, "ELIGIBLE", "Source reviewed",
        "composition-global-eligible-0001"))
    query = ReferenceUseQuery(
        uuid.uuid4(), uuid.uuid4(), created.reference_solution_id,
        created.reference_version_id, "GLOBAL")
    with runtime.unit_of_work() as tx:
        result = proof.prove(tx, query)
        assert result.source_fingerprint == qualified.content_fingerprint
        assert result.deidentification_confirmation_id == confirmed.confirmation_id
        denied(lambda: proof.prove(
            tx, replace(query, reference_version_id=uuid.uuid4())))
    expired_clock = ReferenceUseProofService(
        references=SqlAlchemyCurrentReferenceUseRepository(),
        sources=proof._sources,
        confirmations=SqlAlchemyCurrentGlobalConfirmationRepository(),
        clock=lambda: confirmed.expires_at)
    with runtime.unit_of_work() as tx:
        denied(lambda: expired_clock.prove(tx, query))
    with runtime.unit_of_work() as tx:
        current = SqlAlchemyCurrentReferenceUseRepository().current(
            tx, query=query, now=datetime.now(timezone.utc))
        assert current is not None
        assert current.source_project_class == request.source_project_class
        assert current.deidentification_class == request.deidentification_class
        assert current.applicability == request.applicability
        node = SqlAlchemyEvidenceFixedSourceRepository().get_for_trace(
            tx, scope="GLOBAL", project_id=None,
            evidence_id=request.evidence_ids[1])
        assert node is not None and node.source_parse_record_id is not None
        parsed = SqlAlchemyParseResultReadRepository().get_for_trace(
            tx, scope="GLOBAL", project_id=None,
            document_version_id=node.document_version_id,
            parse_record_id=node.source_parse_record_id)
        assert parsed is not None
    parse_file = parse_results._storage._root / parsed.storage_locator
    original = parse_file.read_bytes()
    try:
        parse_file.write_bytes(original[:-1] + b"!")
        with runtime.unit_of_work() as tx:
            denied(lambda: proof.prove(tx, query))
    finally:
        parse_file.write_bytes(original)
    with runtime.unit_of_work() as tx:
        assert proof.prove(tx, query).source_fingerprint == qualified.content_fingerprint
    return None


def main() -> None:
    project_fixture.main(on_created=project_created)
    global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P02_P03_REFERENCE_USE_COMPOSITION_PASS: PROJECT/GLOBAL "
          "current ledger, fixed real files, Evidence and confirmation")


if __name__ == "__main__":
    main()
