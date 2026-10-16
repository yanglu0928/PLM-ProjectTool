"""Windows 11 disposable PG history read proof for SOL-06."""

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
    "sol06_repo_for_read",
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
    one = reader.get(query, first.structured_solution_spec_id)
    two = reader.get(query, second.structured_solution_spec_id)
    assert one.version_no == 1 and two.version_no == 2
    assert one.spec_series_id == two.spec_series_id
    assert one.version_state == two.version_state == "DRAFT"
    assert one.payload() == two.payload() == first.payload()
    assert one.requirement_refs == second.requirement_refs
    assert one.section_refs == second.section_refs
    assert one.evidence_ids == second.evidence_ids
    assert two.supersedes_version_ref == first.structured_solution_spec_id
    member = reader.get(StructuredSpecReadQuery(member_token, uuid.uuid4(), project),
                        first.structured_solution_spec_id)
    assert member == one
    for denied in (
            StructuredSpecReadQuery(token, uuid.uuid4(), other_project),
            StructuredSpecReadQuery(b"z" * 32, uuid.uuid4(), project)):
        try:
            reader.get(denied, first.structured_solution_spec_id)
        except StructuredSpecReadError as error:
            assert error.code in ("RESOURCE_NOT_FOUND", "AUTH_ACCESS_DENIED"), error.code
        else:
            raise AssertionError("cross-project/invalid Session read was not denied")
    print("SOL_06_A10_P01_READ_PG_PASS: two immutable versions, project member, "
          "cross-project and invalid session denied")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **nested: prior.on_created(
            **nested, on_http=lambda **created: on_created(
                **created, license_guard=kwargs["license_guard"]))))
