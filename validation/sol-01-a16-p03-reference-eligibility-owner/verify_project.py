"""Disposable Win11 PG18 real-source PROJECT Reference eligibility Owner proof."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.application.revise_reference_solution import (
    ReferenceReviseService, ReviseReferenceSolution,
)
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityCommandError, ReferenceEligibilityService, SetReferenceEligibility,
)
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import (
    SqlAlchemyReferenceEligibilityRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import (
    SqlAlchemyReferenceReviseRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_create_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def denied(action, *codes: str) -> None:
    try:
        action()
    except ReferenceEligibilityCommandError as error:
        assert error.code in codes, error.code
    else:
        raise AssertionError("Reference eligibility command was accepted")


def on_created(**facts) -> None:
    auth = ProjectAuthorizationService(
        unit_of_work=facts["runtime"].unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())

    def service(audit=None, guard=None):
        return ReferenceEligibilityService(
            unit_of_work=facts["runtime"].unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=auth,
            license_guard=guard or facts["license_guard"],
            sources=facts["sources"],
            repository=SqlAlchemyReferenceEligibilityRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit or facts["audit"],
        )

    root = facts["created"].reference_solution_id
    command = SetReferenceEligibility(
        facts["token"], facts["csrf"], uuid.uuid4(), "PROJECT",
        facts["project"], root, 0, "ELIGIBLE", "Manager reviewed current sources",
        "eligibility-p03-project-0001",
    )

    class DeniedLicense:
        def require_valid(self, *, trace_id):
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")

    denied(lambda: service(guard=DeniedLicense()).set(command),
           "LICENSE_OPERATION_DENIED")
    denied(lambda: service().set(replace(command, session_token=facts["member_token"],
                                         csrf_token=facts["member_csrf"])),
           "RESOURCE_NOT_FOUND")
    denied(lambda: service().set(replace(command, project_id=facts["other_project"])),
           "RESOURCE_NOT_FOUND")
    denied(lambda: service().set(replace(command, csrf_token=b"x" * 32)),
           "AUTH_ACCESS_DENIED")
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(service().set, command)
        two = pool.submit(service().set, command)
        first = one.result(timeout=30)
        assert two.result(timeout=30) == first
    assert first.eligibility_state == "ELIGIBLE" and first.etag == '"v1"'
    assert service().set(replace(command, trace_id=uuid.uuid4())) == first
    denied(lambda: service().set(replace(command, idempotency_key="other-key-0000000001")),
           "VERSION_CONFLICT")
    denied(lambda: service().set(replace(command, reason="different request")),
           "CONFLICT_IDEMPOTENCY")

    class BrokenAudit:
        def append(self, *_):
            raise RuntimeError("synthetic audit failure")

    restricted = replace(command, expected_lock_version=1,
                         requested_state="RESTRICTED", reason="Review suspended",
                         idempotency_key="eligibility-p03-project-0002")
    denied(lambda: service(audit=BrokenAudit()).set(restricted), "SOLUTION_UNAVAILABLE")
    with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT eligibility_state,lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s", (root,)).fetchone() == ("ELIGIBLE", 1)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_eligibility_events "
            "WHERE reference_solution_id=%s", (root,)).fetchone()[0] == 1
    assert service().set(restricted).etag == '"v2"'
    reeligible = replace(command, expected_lock_version=2,
                         idempotency_key="eligibility-p03-project-0003")
    assert service().set(reeligible).etag == '"v3"'

    revise_service = ReferenceReviseService(
        unit_of_work=facts["runtime"].unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=auth,
        license_guard=facts["license_guard"],
        sources=facts["sources"],
        repository=SqlAlchemyReferenceReviseRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=facts["audit"],
    )
    source = ReferenceSourceRequest(
        facts["token"], uuid.uuid4(), "PROJECT", facts["project"],
        (facts["document_version"],), (facts["evidence"],),
        "PLM", "PROJECT_INTERNAL", {"industry": "synthetic"},
    )
    revision = revise_service.revise(ReviseReferenceSolution(
        source, facts["csrf"], root, 3, "eligibility-revise-0001"))
    assert revision.version_no == 2 and revision.result_lock_version == 4
    with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT eligibility_state,eligibility_reason,current_version_ref,lock_version "
            "FROM plm.sol_reference_solutions WHERE reference_solution_id=%s",
            (root,)).fetchone() == (
                "RESTRICTED", "CURRENT_VERSION_CHANGED_REQUIRES_REVIEW",
                revision.reference_version_id, 4)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_eligibility_events "
            "WHERE reference_solution_id=%s AND event_kind='SYSTEM_INVALIDATION'",
            (root,)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE target_object_id=%s AND action='SOL_REFERENCE_ELIGIBILITY_INVALIDATED'",
            (root,)).fetchone()[0] == 1
    assert service().set(replace(command, trace_id=uuid.uuid4())) == first
    new_eligibility = replace(
        command, expected_lock_version=4,
        idempotency_key="eligibility-p03-project-0004")
    file_path = facts["scratch"] / "private-documents" / facts["locator"]
    original_bytes = file_path.read_bytes()
    try:
        file_path.write_bytes(b"X" * len(original_bytes))
        denied(lambda: service().set(new_eligibility),
               "RESOURCE_NOT_FOUND", "SOURCE_UNAVAILABLE")
    finally:
        file_path.write_bytes(original_bytes)
    assert service().set(new_eligibility).etag == '"v5"'
    revoked = replace(
        command, expected_lock_version=5, requested_state="REVOKED",
        reason="Manager revoked identity",
        idempotency_key="eligibility-p03-project-0005")
    assert service().set(revoked).etag == '"v6"'
    denied(lambda: service().set(replace(
        command, expected_lock_version=6,
        idempotency_key="eligibility-p03-project-0006")),
        "CONFLICT_STATE")
    return None


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("SOL_01_A16_P03_REFERENCE_ELIGIBILITY_PROJECT_PG_PASS")
