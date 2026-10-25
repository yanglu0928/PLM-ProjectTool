"""Disposable PG GLOBAL Reference revision with bound human confirmation."""

from __future__ import annotations

import importlib.util
import uuid
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
from plm_assistant.modules.solution.application.revise_reference_solution import (
    ReferenceReviseError, ReferenceReviseService, ReviseReferenceSolution,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_source_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_qualified(*, runtime, request, sources, audit, license_guard,
                 confirmed, port, **_unused) -> None:
    auth = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=auth, license_guard=license_guard,
        sources=sources, receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    creates = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository())
    revises = ReferenceReviseService(
        **common, repository=SqlAlchemyReferenceReviseRepository())
    initial = creates.create(CreateReferenceSolution(
        request, fixture.CSRF, "Global Reference", "global-initial-0001"))
    command = ReviseReferenceSolution(
        request, fixture.CSRF, initial.reference_solution_id, 0,
        "global-revise-0001")
    revised = revises.revise(command)
    assert revised.version_no == 2 and revised.scope == "GLOBAL"
    assert revises.revise(replace(
        command, sources=replace(request, trace_id=uuid.uuid4()))) == revised
    # Same confirmation cannot be reused for a changed source fingerprint.
    try:
        revises.revise(replace(
            command, sources=replace(request, evidence_ids=(request.evidence_ids[0],)),
            expected_lock_version=1, idempotency_key="global-revise-0002"))
    except ReferenceReviseError as error:
        assert error.code == "RESOURCE_NOT_FOUND", error.code
    else:
        raise AssertionError("GLOBAL revision accepted unconfirmed changed sources")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT deidentification_confirmation_id FROM plm.sol_reference_versions "
            "WHERE reference_version_id=%s", (revised.reference_version_id,)
        ).fetchone()[0] == confirmed.confirmation_id
        assert db.execute(
            "SELECT current_version_ref,lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s", (initial.reference_solution_id,)
        ).fetchone() == (revised.reference_version_id, 1)
    print("SOL_01_A07_REFERENCE_REVISE_GLOBAL_PG_PASS")


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
