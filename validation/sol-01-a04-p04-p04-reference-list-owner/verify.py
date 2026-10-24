"""Disposable PG18 proof of authorized PROJECT Reference keyset list owner."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceReadError, ReferenceReadQuery, ReferenceReadService,
)
from plm_assistant.modules.solution.infrastructure.reference_read_repository import SqlAlchemyReferenceReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
project_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_fixture)


def rejected(code: str, action) -> None:
    try:
        action()
    except ReferenceReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("Reference list incorrectly accepted")


def on_created(*, port, runtime, license_guard, project, other_project,
               member, created, member_created, token, member_token,
               **_unused) -> int:
    service = ReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyReferenceReadRepository())
    query = ReferenceReadQuery(token, uuid.uuid4(), project)
    whole = service.list_current(query)
    expected = {created.reference_solution_id, member_created.reference_solution_id}
    assert len(whole.items) == 2
    assert {item.reference_solution_id for item in whole.items} == expected
    assert [item.reference_solution_id.int for item in whole.items] == sorted(
        item.reference_solution_id.int for item in whole.items)
    assert whole.next_after_reference_solution_id is None and not whole.has_more
    assert all(item.project_id == project and item.scope == "PROJECT"
               and item.version_state == "DRAFT" and item.etag == '"v0"'
               for item in whole.items)
    first = service.list_current(query, limit=1)
    assert len(first.items) == 1 and first.has_more
    assert first.next_after_reference_solution_id == first.items[0].reference_solution_id
    second = service.list_current(
        query, after_reference_solution_id=first.next_after_reference_solution_id,
        limit=1)
    assert len(second.items) == 1 and not second.has_more
    assert first.items + second.items == whole.items
    assert service.list_current(query, after_reference_solution_id=
        second.items[0].reference_solution_id, limit=1).items == ()
    assert service.list_current(
        ReferenceReadQuery(member_token, uuid.uuid4(), project)).items == whole.items
    assert service.list_current(
        ReferenceReadQuery(b"u" * 32, uuid.uuid4(), project)).items == whole.items
    rejected("RESOURCE_NOT_FOUND", lambda: service.list_current(
        ReferenceReadQuery(token, uuid.uuid4(), other_project)))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    rejected("RESOURCE_NOT_FOUND", lambda: service.list_current(
        ReferenceReadQuery(member_token, uuid.uuid4(), project)))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    return 0


def main() -> None:
    project_fixture.main(on_created=on_created)
    print("SOL_01_A04_P04_P04_REFERENCE_LIST_OWNER_PG_PASS: stable keyset, "
          "same-project members, cross-project and suspended member denied")


if __name__ == "__main__":
    main()
