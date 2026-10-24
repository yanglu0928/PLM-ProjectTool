"""Win11 disposable PostgreSQL GLOBAL publication Owner with real sources."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateService,
)
from plm_assistant.modules.solution.application.set_global_reference_publication import (
    GlobalReferencePublicationError, GlobalReferencePublicationService,
    SetGlobalReferencePublication,
)
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityService, SetReferenceEligibility,
)
from plm_assistant.modules.solution.infrastructure.global_reference_publication_repository import (
    SqlAlchemyGlobalReferencePublicationRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_publication_real_sources_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def denied(action, *codes: str) -> None:
    try:
        action()
    except GlobalReferencePublicationError as error:
        assert error.code in codes, error.code
    else:
        raise AssertionError("GLOBAL publication unexpectedly accepted")


def on_qualified(*, runtime, request, sources, audit, license_guard,
                 confirmed, qualified, port, downloads, **_unused) -> None:
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    initial = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(
                request, fixture.CSRF, "Synthetic publication source",
                "global-publication-create-0001"))
    eligibility = ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository())
    decided = eligibility.set(SetReferenceEligibility(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
        initial.reference_solution_id, 0, "ELIGIBLE",
        "Admin reviewed source", "global-publication-eligible-0001"))
    assert decided.reference_version_id == initial.reference_version_id
    publication = GlobalReferencePublicationService(
        unit_of_work=runtime.unit_of_work,
        admin=SqlAlchemyLicenseImportAccess(), license_guard=license_guard,
        sources=sources,
        repository=SqlAlchemyGlobalReferencePublicationRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    command = SetGlobalReferencePublication(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(),
        initial.reference_solution_id, initial.reference_version_id,
        0, "PUBLISH", "已审定的非敏感合成方案", "管理员人工核查",
        "global-publication-publish-0001")
    denied(lambda: publication.set(replace(
        command, session_token=b"x" * 32, csrf_token=b"y" * 32)),
        "AUTH_ACCESS_DENIED")
    denied(lambda: publication.set(replace(
        command, expected_reference_version_id=uuid.uuid4())),
        "VERSION_CONFLICT")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        locator = db.execute(
            "SELECT f.storage_locator FROM plm.doc_document_versions v "
            "JOIN plm.doc_file_objects f ON f.file_object_id=v.file_object_id "
            "WHERE v.document_version_id=%s", (request.document_version_ids[0],)
        ).fetchone()[0]
    path = downloads._storage._root / locator
    original = path.read_bytes()
    try:
        path.write_bytes(b"X" * len(original))
        denied(lambda: publication.set(command),
               "RESOURCE_NOT_FOUND", "SOURCE_UNAVAILABLE")
    finally:
        path.write_bytes(original)
    published = publication.set(command)
    assert published.event_no == 1 and published.event_kind == "PUBLISH"
    assert published.display_label == "已审定的非敏感合成方案"
    assert publication.set(replace(command, trace_id=uuid.uuid4())) == published
    denied(lambda: publication.set(replace(
        command, expected_event_no=1,
        idempotency_key="global-publication-publish-0002")),
        "CONFLICT_STATE")
    restricted = eligibility.set(SetReferenceEligibility(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
        initial.reference_solution_id, 1, "RESTRICTED",
        "Admin withheld candidate use", "global-publication-restrict-0001"))
    assert restricted.result_lock_version == 2
    denied(lambda: publication.set(replace(
        command, expected_event_no=1,
        idempotency_key="global-publication-publish-0003")),
        "CONFLICT_STATE")
    revoke = SetGlobalReferencePublication(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(),
        initial.reference_solution_id, initial.reference_version_id,
        1, "REVOKE", None, "管理员撤回候选可见性",
        "global-publication-revoke-0001")
    revoked = publication.set(revoke)
    assert revoked.event_no == 2 and revoked.event_kind == "REVOKE"
    assert publication.set(replace(revoke, trace_id=uuid.uuid4())) == revoked
    assert publication.set(replace(command, trace_id=uuid.uuid4())) == published
    reeligible = eligibility.set(SetReferenceEligibility(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
        initial.reference_solution_id, 2, "ELIGIBLE",
        "Admin reverified sources", "global-publication-reeligible-0001"))
    assert reeligible.result_lock_version == 3
    republish = replace(
        command, expected_event_no=2, display_label="复核后的合成方案标签",
        idempotency_key="global-publication-publish-0004")

    class FailingAudit:
        def append(self, *_args, **_kwargs):
            raise RuntimeError("synthetic audit failure")

    failing = GlobalReferencePublicationService(
        unit_of_work=runtime.unit_of_work,
        admin=SqlAlchemyLicenseImportAccess(), license_guard=license_guard,
        sources=sources,
        repository=SqlAlchemyGlobalReferencePublicationRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=FailingAudit())
    denied(lambda: failing.set(republish), "SOLUTION_UNAVAILABLE")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_global_reference_publication_events "
            "WHERE reference_solution_id=%s", (initial.reference_solution_id,)
        ).fetchone()[0] == 2
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(publication.set, republish) for _ in range(2)]
        results = [task.result(timeout=30) for task in tasks]
    assert results[0] == results[1]
    republished = results[0]
    assert republished.event_no == 3 and republished.display_label == "复核后的合成方案标签"
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT event_no,event_kind,display_label FROM "
            "plm.sol_global_reference_publication_events "
            "WHERE reference_solution_id=%s ORDER BY event_no",
            (initial.reference_solution_id,)).fetchall() == [
                (1, "PUBLISH", "已审定的非敏感合成方案"),
                (2, "REVOKE", None),
                (3, "PUBLISH", "复核后的合成方案标签")]
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "target_object_id=%s AND action='SOL_GLOBAL_REFERENCE_PUBLICATION_SET'",
            (initial.reference_solution_id,)).fetchone()[0] == 3
    print("SOL_03_A04_P03_P03_P06_A03_P02_GLOBAL_PUBLICATION_OWNER_PASS: "
          "real Session, License, sources, confirmation, event/Audit/receipt, "
          "tamper refusal, concurrent replay, restricted-state revoke and Audit rollback")


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
