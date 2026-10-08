"""Win11 isolated PG list keyset through the dedicated signed cursor."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.application.read_outline import OutlineReadQuery, OutlineReadService
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_list_owner_fixture",
    ROOT / "validation/sol-02-a06-p04-outline-list-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(*, runtime, license_guard, project, token, **kwargs):
    prior.on_created(runtime=runtime, license_guard=license_guard,
                     project=project, token=token, **kwargs)
    reader = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyOutlineReadRepository())
    codec = OutlineListCursorCodec(b"q" * 32)
    query = OutlineReadQuery(token, uuid.uuid4(), project)
    first = reader.list_current(query, limit=1)
    assert first.has_more and first.next_after_outline_id is not None
    cursor = codec.encode(
        session_token=token, project_id=project, page_size=1,
        outline_id=first.next_after_outline_id)
    after = codec.decode(cursor, session_token=token,
                         project_id=project, page_size=1)
    second = reader.list_current(query, after_outline_id=after, limit=1)
    assert len(second.items) == 1
    assert second.items[0].solution_outline_id.int > first.items[0].solution_outline_id.int
    try:
        codec.decode(cursor, session_token=token,
                     project_id=project, page_size=2)
    except ApplicationError as error:
        assert error.spec.code == "REQUEST_MALFORMED"
    else:
        raise AssertionError("cursor must bind page size")
    return 0


if __name__ == "__main__":
    prior.prior.prior.main(on_created=on_created)
    print("SOL_02_A06_P05_OUTLINE_LIST_CURSOR_PASS: isolated PG keyset "
          "with signed Session/project/query-bound cursor")
