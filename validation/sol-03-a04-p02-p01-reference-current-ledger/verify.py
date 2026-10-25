"""Disposable PG proof for Solution-owned current Reference use ledgers."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateService,
)
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseQuery
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityService, SetReferenceEligibility,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import (
    SqlAlchemyCurrentGlobalConfirmationRepository,
    SqlAlchemyCurrentReferenceUseRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


project_fixture = module(
    "project_reference_fixture",
    "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
global_fixture = module(
    "global_reference_fixture",
    "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")


def eligibility_service(*, runtime, sources, audit, license_guard):
    return ReferenceEligibilityService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        repository=SqlAlchemyReferenceEligibilityRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )


def project_created(*, runtime, sources, audit, license_guard,
                    created, project, other_project, token, csrf, **_facts):
    service = eligibility_service(
        runtime=runtime, sources=sources, audit=audit,
        license_guard=license_guard)
    service.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 0, "ELIGIBLE", "Current project source reviewed",
        "outline-use-project-eligibility-0001"))
    reader = SqlAlchemyCurrentReferenceUseRepository()
    now = datetime.now(timezone.utc)
    query = ReferenceUseQuery(
        uuid.uuid4(), project, created.reference_solution_id,
        created.reference_version_id, "PROJECT")
    with runtime.unit_of_work() as tx:
        current = reader.current(tx, query=query, now=now)
        assert current is not None
        assert current.eligibility_state == current.eligibility_event_result_state == "ELIGIBLE"
        assert current.reference_version_id == current.eligibility_event_version_id
        assert current.source_project_id == project
        assert current.document_version_ids
        assert reader.current(tx, query=replace(query, target_project_id=other_project), now=now) is None
        assert reader.current(tx, query=replace(query, reference_version_id=uuid.uuid4()), now=now) is None
        assert SqlAlchemyCurrentGlobalConfirmationRepository().current(
            tx, current=current, now=now) is None
    service.set(SetReferenceEligibility(
        token, csrf, uuid.uuid4(), "PROJECT", project,
        created.reference_solution_id, 1, "RESTRICTED", "No longer approved",
        "outline-use-project-eligibility-0002"))
    with runtime.unit_of_work() as tx:
        assert reader.current(tx, query=query, now=now) is None
    return 0


def global_qualified(*, runtime, request, sources, audit, license_guard,
                     qualified, confirmed, **_facts):
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    created = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(request, global_fixture.CSRF,
                                    "Outline use global", "outline-use-global-create-0001"))
    ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository()).set(
            SetReferenceEligibility(
                global_fixture.TOKEN, global_fixture.CSRF, uuid.uuid4(),
                "GLOBAL", None, created.reference_solution_id, 0,
                "ELIGIBLE", "Current global source reviewed",
                "outline-use-global-eligibility-0001"))
    now = datetime.now(timezone.utc)
    query = ReferenceUseQuery(
        uuid.uuid4(), uuid.uuid4(), created.reference_solution_id,
        created.reference_version_id, "GLOBAL")
    reader = SqlAlchemyCurrentReferenceUseRepository()
    with runtime.unit_of_work() as tx:
        current = reader.current(tx, query=query, now=now)
        assert current is not None
        assert current.source_project_id is None
        assert current.deidentification_confirmation_id == confirmed.confirmation_id
        assert current.source_fingerprint == qualified.content_fingerprint
        confirmation = SqlAlchemyCurrentGlobalConfirmationRepository().current(
            tx, current=current, now=now)
        assert confirmation is not None
        assert confirmation.confirmation_id == confirmed.confirmation_id
        assert confirmation.source_fingerprint == current.source_fingerprint
        assert confirmation.revoked_at is None
        assert confirmation.confirmed_at <= now < confirmation.expires_at
        assert reader.current(tx, query=replace(query, scope="PROJECT"), now=now) is None


def main() -> None:
    project_fixture.main(on_created=project_created)
    global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P02_P01_CURRENT_REFERENCE_LEDGER_PASS: PROJECT/GLOBAL "
          "current version/event, isolation, restriction and latest confirmation")


if __name__ == "__main__":
    main()
