"""Isolated PG18/real Auth projection of a synthetic GLOBAL Reference."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.read_global_reference import (
    GlobalReferenceReadError, GlobalReferenceReadQuery, GlobalReferenceReadService,
)
from plm_assistant.modules.solution.infrastructure.global_reference_read_repository import (
    SqlAlchemyGlobalReferenceReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_create_pg",
    ROOT / "validation/sol-01-a04-p08-p06-p03-global-reference-create-http-pg/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
PROJECT_SPEC = importlib.util.spec_from_file_location(
    "project_reference_create_pg",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert PROJECT_SPEC and PROJECT_SPEC.loader
project_fixture = importlib.util.module_from_spec(PROJECT_SPEC)
PROJECT_SPEC.loader.exec_module(project_fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def check(*, runtime, license_guard, result, document, version, evidence,
          node_evidence, confirmation_id, **_unused):
    repository = SqlAlchemyGlobalReferenceReadRepository()
    service = GlobalReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        admins=SqlAlchemyDeploymentReadAccess(),
        license_guard=license_guard, repository=repository)
    query = GlobalReferenceReadQuery(base.fixture.TOKEN, uuid.uuid4())
    identity = uuid.UUID(result["reference_solution_id"])
    current = service.get_current(query, identity)
    assert current.reference_solution_id == identity
    assert current.reference_version_id == uuid.UUID(result["reference_version_id"])
    assert current.name == result["name"]
    assert current.eligibility_state == "REFERENCE_ONLY"
    assert current.version_state == "DRAFT" and current.etag == '"v0"'
    assert current.deidentification_confirmation_id == uuid.UUID(confirmation_id)
    assert tuple((item.document_id, item.document_version_id)
                 for item in current.document_refs) == ((document, version),)
    assert current.evidence_ids == (evidence, node_evidence)
    page = service.list_current(query)
    assert len(page.items) == 1 and page.items[0].reference_solution_id == identity
    assert not page.has_more and page.next_after_reference_solution_id is None
    assert service.list_current(query, after_reference_solution_id=identity).items == ()
    for denied_query, expected in (
            (GlobalReferenceReadQuery(b"x" * 32, uuid.uuid4()), "RESOURCE_NOT_FOUND"),
            (GlobalReferenceReadQuery(b"bad", uuid.uuid4()), "VALIDATION_FAILED")):
        try:
            service.get_current(denied_query, identity)
        except GlobalReferenceReadError as error:
            assert error.code == expected
        else:
            raise AssertionError("unauthorized GLOBAL Reference read succeeded")
    try:
        service.get_current(query, uuid.uuid4())
    except GlobalReferenceReadError as error:
        assert error.code == "RESOURCE_NOT_FOUND"
    else:
        raise AssertionError("missing GLOBAL Reference read succeeded")
    denied = GlobalReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        admins=SqlAlchemyDeploymentReadAccess(),
        license_guard=DeniedLicense(), repository=repository)
    try:
        denied.list_current(query)
    except GlobalReferenceReadError as error:
        assert error.code == "LICENSE_OPERATION_DENIED"
    else:
        raise AssertionError("denied License GLOBAL Reference list succeeded")


def on_preview(**kwargs) -> None:
    base.on_preview(**kwargs, on_created=check, on_revoked=check)


def project_scope_check(*, runtime, created, **_unused) -> None:
    repository = SqlAlchemyGlobalReferenceReadRepository()
    with runtime.unit_of_work() as tx:
        assert repository.get_current(
            tx, reference_solution_id=created.reference_solution_id) is None
        page = repository.list_current(
            tx, after_reference_solution_id=None, limit=50)
        assert page.items == () and page.next_after_reference_solution_id is None
        assert not page.has_more


def main() -> None:
    base.fixture.main(on_preview=on_preview)
    project_fixture.main(on_created=project_scope_check)
    print("SOL_01_A04_P09_P02_GLOBAL_REFERENCE_READ_PG_PASS: real Admin "
          "Session, GLOBAL fixed refs, ordered list, revoked-confirmation "
          "historical read, PROJECT scope exclusion, unauthorized and License denial")


if __name__ == "__main__":
    main()
