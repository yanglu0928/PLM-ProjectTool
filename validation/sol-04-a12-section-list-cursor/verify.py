"""Win11 isolated PG Section keyset through a dedicated signed cursor."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.application.read_section import SectionReadQuery, SectionReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_list_owner_fixture",
    ROOT / "validation/sol-04-a11-section-list-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(*, runtime, license_guard, project, token, **kwargs) -> int:
    prior.on_created(runtime=runtime, license_guard=license_guard,
                     project=project, token=token, **kwargs)
    reader = SectionReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemySectionReadRepository())
    codec = SectionListCursorCodec(b"q" * 32)
    query = SectionReadQuery(token, uuid.uuid4(), project)
    first = reader.list_current(query, limit=1)
    assert first.has_more and first.next_after_section_id is not None
    cursor = codec.encode(session_token=token, project_id=project,
                          page_size=1, section_id=first.next_after_section_id)
    after = codec.decode(cursor, session_token=token,
                         project_id=project, page_size=1)
    second = reader.list_current(query, after_section_id=after, limit=1)
    assert len(second.items) == 1
    assert second.items[0].solution_section_id.int > first.items[0].solution_section_id.int
    try:
        codec.decode(cursor, session_token=token, project_id=project, page_size=2)
    except ApplicationError as error:
        assert error.spec.code == "REQUEST_MALFORMED"
    else:
        raise AssertionError("cursor must bind page size")
    return 0


if __name__ == "__main__":
    prior.prior.fixture.main(on_created=on_created)
    print("SOL_04_A12_SECTION_LIST_CURSOR_PASS: isolated PG keyset "
          "with signed Session/project/query-bound Section cursor")
