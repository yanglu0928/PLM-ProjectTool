"""Disposable PG GLOBAL Reference eligibility with current human confirmation."""

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
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityCommandError, ReferenceEligibilityService, SetReferenceEligibility,
)
from plm_assistant.modules.solution.application.revise_reference_solution import (
    ReferenceReviseService, ReviseReferenceSolution,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_source_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def denied(action, *codes: str) -> None:
    try:
        action()
    except ReferenceEligibilityCommandError as error:
        assert error.code in codes, error.code
    else:
        raise AssertionError("GLOBAL Reference eligibility was accepted")


def on_qualified(*, runtime, request, sources, audit, license_guard,
                 confirmed, port, qualified, downloads, **_unused) -> None:
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
    service = ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository())
    initial = creates.create(CreateReferenceSolution(
        request, fixture.CSRF, "Eligibility Global", "global-eligibility-create-0001"))
    assert initial.deidentification_confirmation_id == confirmed.confirmation_id
    cmd = SetReferenceEligibility(
        fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
        initial.reference_solution_id, 0, "ELIGIBLE", "Admin verified current deidentification",
        "global-eligibility-decision-0001",
    )
    denied(lambda: service.set(replace(cmd, session_token=b"x" * 32,
                                       csrf_token=b"y" * 32)),
           "AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND")
    denied(lambda: service.set(replace(cmd, csrf_token=b"x" * 32)),
           "AUTH_ACCESS_DENIED")
    eligible = service.set(cmd)
    assert eligible.etag == '"v1"' and eligible.eligibility_state == "ELIGIBLE"
    assert service.set(replace(cmd, trace_id=uuid.uuid4())) == eligible
    restricted = service.set(replace(
        cmd, expected_lock_version=1, requested_state="RESTRICTED",
        reason="Admin withheld use", idempotency_key="global-eligibility-decision-0002"))
    assert restricted.etag == '"v2"'
    assert service.set(replace(cmd, trace_id=uuid.uuid4())) == eligible
    reeligible = replace(
        cmd, expected_lock_version=2,
        idempotency_key="global-eligibility-decision-0003")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        locator = db.execute(
            "SELECT f.storage_locator FROM plm.doc_document_versions v "
            "JOIN plm.doc_file_objects f ON f.file_object_id=v.file_object_id "
            "WHERE v.document_version_id=%s", (request.document_version_ids[0],)
        ).fetchone()[0]
    file_path = downloads._storage._root / locator
    original = file_path.read_bytes()
    try:
        file_path.write_bytes(b"X" * len(original))
        denied(lambda: service.set(reeligible), "RESOURCE_NOT_FOUND", "SOURCE_UNAVAILABLE")
    finally:
        file_path.write_bytes(original)
    again = service.set(reeligible)
    assert again.etag == '"v3"'
    suspended = service.set(replace(
        cmd, expected_lock_version=3, requested_state="RESTRICTED",
        reason="Confirmation recheck", idempotency_key="global-eligibility-decision-0004"))
    assert suspended.etag == '"v4"'
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute(
            "UPDATE plm.sol_reference_deidentification_confirmations "
            "SET revoked_at=statement_timestamp() WHERE confirmation_id=%s",
            (confirmed.confirmation_id,))
    try:
        denied(lambda: service.set(replace(
            cmd, expected_lock_version=4,
            idempotency_key="global-eligibility-decision-0005")),
            "RESOURCE_NOT_FOUND", "SOURCE_UNAVAILABLE")
    finally:
        # Test-only restore in the disposable database so the upstream source
        # fixture can independently exercise its legitimate revocation flow.
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            table = "plm.sol_reference_deidentification_confirmations"
            trigger = "trg_sol_reference_deidentification_confirmations__owner"
            db.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
            try:
                db.execute(f"UPDATE {table} SET revoked_at=NULL WHERE confirmation_id=%s",
                           (confirmed.confirmation_id,))
            finally:
                db.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    assert service.set(replace(
        cmd, expected_lock_version=4,
        idempotency_key="global-eligibility-decision-0005")).etag == '"v5"'
    revises = ReferenceReviseService(
        **common, repository=SqlAlchemyReferenceReviseRepository())
    revise_command = ReviseReferenceSolution(
        request, fixture.CSRF, initial.reference_solution_id, 5,
        "global-eligibility-revise-0001")
    revision = revises.revise(revise_command)
    assert revision.version_no == 2 and revision.result_lock_version == 6
    assert revises.revise(replace(
        revise_command, sources=replace(request, trace_id=uuid.uuid4()))) == revision
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT eligibility_state,lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s",
            (initial.reference_solution_id,)).fetchone() == ("RESTRICTED", 6)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_eligibility_events "
            "WHERE reference_solution_id=%s AND event_kind='HUMAN'",
            (initial.reference_solution_id,)).fetchone()[0] == 5
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_eligibility_events "
            "WHERE reference_solution_id=%s AND event_kind='SYSTEM_INVALIDATION'",
            (initial.reference_solution_id,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT deidentification_confirmation_id,source_fingerprint "
            "FROM plm.sol_reference_versions WHERE reference_version_id=%s",
            (initial.reference_version_id,)).fetchone() == (
                confirmed.confirmation_id, qualified.content_fingerprint)
    print("SOL_01_A16_P03_REFERENCE_ELIGIBILITY_GLOBAL_PG_PASS")


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
