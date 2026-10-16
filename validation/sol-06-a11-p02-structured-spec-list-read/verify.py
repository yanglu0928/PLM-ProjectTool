"""Windows 11 disposable PG proof for authorized SOL-06 version listing."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecReadError, StructuredSpecReadQuery, StructuredSpecReadService,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_read_repository import (
    SqlAlchemyStructuredSpecReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_repo_for_list",
    ROOT / "validation/sol-06-a09-p02-structured-spec-repository/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(*, runtime, license_guard, project, other_project,
               token, member_token, first, second, **_unused) -> None:
    reader = StructuredSpecReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        specs=SqlAlchemyStructuredSpecReadRepository())
    query = StructuredSpecReadQuery(token, uuid.uuid4(), project)
    first_page = reader.list_versions(query, limit=1)
    assert len(first_page.items) == 1 and first_page.has_more
    assert first_page.next_before_spec_id == first_page.items[-1].structured_solution_spec_id
    second_page = reader.list_versions(
        query, before_spec_id=first_page.next_before_spec_id, limit=1)
    assert len(second_page.items) == 1 and not second_page.has_more
    assert second_page.next_before_spec_id is None
    listed = first_page.items + second_page.items
    assert {item.structured_solution_spec_id for item in listed} == {
        first.structured_solution_spec_id, second.structured_solution_spec_id}
    assert listed[0].structured_solution_spec_id.int > listed[1].structured_solution_spec_id.int
    assert all(item.project_id == project and item.spec_type == "MIGRATION_SPEC"
               and item.version_state == "DRAFT" for item in listed)
    member = reader.list_versions(
        StructuredSpecReadQuery(member_token, uuid.uuid4(), project), limit=10)
    assert {item.structured_solution_spec_id for item in member.items} == {
        first.structured_solution_spec_id, second.structured_solution_spec_id}
    for denied in (
            StructuredSpecReadQuery(token, uuid.uuid4(), other_project),
            StructuredSpecReadQuery(b"z" * 32, uuid.uuid4(), project)):
        try:
            reader.list_versions(denied, limit=10)
        except StructuredSpecReadError as error:
            assert error.code in ("RESOURCE_NOT_FOUND", "AUTH_ACCESS_DENIED"), error.code
        else:
            raise AssertionError("cross-project/invalid Session list was not denied")
    print("SOL_06_A11_P02_LIST_READ_PG_PASS: all immutable versions, descending "
          "keyset pages, project member, cross-project and invalid session denied")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **nested: prior.on_created(
            **nested, on_http=lambda **created: on_created(
                **created, license_guard=kwargs["license_guard"]))))
