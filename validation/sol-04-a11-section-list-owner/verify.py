"""Win11 disposable PG proof of authorized Section keyset LIST owner."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_section import CreateSection, SectionCreateService
from plm_assistant.modules.solution.application.read_section import (
    SectionReadError, SectionReadQuery, SectionReadService,
)
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_read_owner_fixture",
    ROOT / "validation/sol-04-a07-section-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def rejects(code: str, action) -> None:
    try:
        action()
    except SectionReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               member, token, csrf, member_token, **kwargs) -> int:
    prior.on_created(port=port, runtime=runtime, audit=audit,
                     license_guard=license_guard, project=project,
                     other_project=other_project, member=member,
                     token=token, csrf=csrf, member_token=member_token,
                     **kwargs)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        outline_id = db.execute(
            "SELECT solution_outline_id FROM plm.sol_outlines WHERE "
            "project_id=%s AND name='Read section parent'", (project,)).fetchone()[0]
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    creates = SectionCreateService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemySectionCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    for index in (2, 3):
        creates.create(CreateSection(
            token, csrf, uuid.uuid4(), project, outline_id,
            f"Section {index}", f"section-list-{index:04d}"))
    reads = dict(unit_of_work=runtime.unit_of_work,
                 access=SqlAlchemyProjectReadAccess(),
                 license_guard=license_guard, authorization=authorization,
                 repository=SqlAlchemySectionReadRepository())
    service = SectionReadService(**reads)
    query = SectionReadQuery(token, uuid.uuid4(), project)
    first = service.list_current(query, limit=1)
    assert len(first.items) == 1 and first.has_more
    assert first.next_after_section_id == first.items[-1].solution_section_id
    second = service.list_current(query, after_section_id=first.next_after_section_id,
                                  limit=1)
    assert len(second.items) == 1 and second.has_more
    third = service.list_current(query, after_section_id=second.next_after_section_id,
                                 limit=1)
    assert len(third.items) == 1 and not third.has_more
    assert third.next_after_section_id is None
    identities = [item.solution_section_id for page in (first, second, third)
                  for item in page.items]
    assert len(set(identities)) == 3 and identities == sorted(identities)
    assert all(item.project_id == project and item.solution_outline_id == outline_id
               and item.current_approved_version_ref is None
               for page in (first, second, third) for item in page.items)
    assert service.list_current(query).items == tuple(
        item for page in (first, second, third) for item in page.items)
    assert service.list_current(query, after_section_id=identities[-1],
                                limit=2).items == ()
    assert len(service.list_current(
        SectionReadQuery(member_token, uuid.uuid4(), project)).items) == 3
    assert len(service.list_current(
        SectionReadQuery(b"u" * 32, uuid.uuid4(), project)).items) == 3
    rejects("VALIDATION_FAILED", lambda: service.list_current(query, limit=0))
    rejects("VALIDATION_FAILED", lambda: service.list_current(
        query, after_section_id=uuid.UUID(int=0)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.list_current(
        replace(query, project_id=other_project)))
    rejects("AUTH_ACCESS_DENIED", lambda: service.list_current(
        replace(query, session_token=b"z" * 32)))
    rejects("LICENSE_OPERATION_DENIED", lambda: SectionReadService(
        **{**reads, "license_guard": DeniedLicense()}).list_current(query))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    rejects("RESOURCE_NOT_FOUND", lambda: service.list_current(
        SectionReadQuery(member_token, uuid.uuid4(), project)))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
        db.execute("ALTER TABLE plm.sol_sections DISABLE TRIGGER ALL")
        try:
            db.execute("UPDATE plm.sol_sections SET current_approved_version_ref=%s "
                       "WHERE solution_section_id=%s", (uuid.uuid4(), identities[0]))
            rejects("SOLUTION_UNAVAILABLE", lambda: service.list_current(query, limit=1))
            db.execute("UPDATE plm.sol_sections SET current_approved_version_ref=NULL "
                       "WHERE solution_section_id=%s", (identities[0],))
        finally:
            db.execute("ALTER TABLE plm.sol_sections ENABLE TRIGGER ALL")
    return 0


if __name__ == "__main__":
    prior.fixture.main(on_created=on_created)
    print("SOL_04_A11_SECTION_LIST_OWNER_PASS: real Session/PG, three-page "
          "keyset, members, isolation, License and pointer corruption denial")
