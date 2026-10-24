"""Win11 isolated PG keyset proof for SolutionOutline list Owner."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.read_outline import OutlineReadError, OutlineReadQuery, OutlineReadService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_read_owner_fixture",
    ROOT / "validation/sol-02-a06-p01-outline-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def rejects(code, action):
    try:
        action()
    except OutlineReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, runtime, audit, license_guard, project,
               other_project, token, csrf, member_token, **kwargs):
    prior.on_created(runtime=runtime, audit=audit,
                     license_guard=license_guard, project=project,
                     other_project=other_project, token=token, csrf=csrf,
                     member_token=member_token, **kwargs)
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    creator = OutlineCreateService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyOutlineCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    second = creator.create(CreateOutline(
        token, csrf, uuid.uuid4(), project, "Second outline", "s" * 16))
    third = creator.create(CreateOutline(
        token, csrf, uuid.uuid4(), project, "Third outline", "t" * 16))
    reader = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyOutlineReadRepository())
    query = OutlineReadQuery(token, uuid.uuid4(), project)
    all_page = reader.list_current(query)
    assert len(all_page.items) == 3 and not all_page.has_more
    assert all_page.next_after_outline_id is None
    assert [item.solution_outline_id for item in all_page.items] == sorted(
        (item.solution_outline_id for item in all_page.items), key=lambda value: value.int)
    assert {item.name for item in all_page.items} == {
        "Read target", "Second outline", "Third outline"}
    assert {item.solution_outline_id for item in all_page.items}.issuperset({
        second.solution_outline_id, third.solution_outline_id})
    cursor = None
    paged = []
    for index in range(3):
        page = reader.list_current(query, after_outline_id=cursor, limit=1)
        assert len(page.items) == 1
        paged.append(page.items[0])
        assert page.has_more == (index < 2)
        cursor = page.next_after_outline_id
    assert tuple(paged) == all_page.items
    assert reader.list_current(query, after_outline_id=paged[-1].solution_outline_id,
                               limit=1).items == ()
    rejects("RESOURCE_NOT_FOUND", lambda: reader.list_current(
        OutlineReadQuery(token, uuid.uuid4(), other_project)))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.list_current(
        OutlineReadQuery(member_token, uuid.uuid4(), project)))
    rejects("VALIDATION_FAILED", lambda: reader.list_current(query, limit=101))
    return 0


if __name__ == "__main__":
    prior.prior.main(on_created=on_created)
    print("SOL_02_A06_P04_OUTLINE_LIST_OWNER_PASS: real PG/Session, "
          "three identities, UUID keyset, empty tail and denied scopes")
