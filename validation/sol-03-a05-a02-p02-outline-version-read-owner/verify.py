"""Disposable Win11 PG check of authorized PROJECT/GLOBAL OutlineVersion reads."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.solution.application.read_outline_version import (
    OutlineVersionReadError, OutlineVersionReadQuery,
    OutlineVersionReadService,
)
from plm_assistant.modules.solution.infrastructure.outline_read_repository import (
    SqlAlchemyOutlineReadRepository,
)
from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import (
    SqlAlchemyOutlineVersionReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_history_repo_for_owner",
    ROOT / "validation/sol-03-a05-a02-p01-outline-version-history-repository/verify.py")
assert SPEC and SPEC.loader
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def _service(runtime, license_guard):
    return OutlineVersionReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        outlines=SqlAlchemyOutlineReadRepository(),
        versions=SqlAlchemyOutlineVersionReadRepository(),
    )


def _reject(code, action):
    try:
        action()
    except OutlineVersionReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected OutlineVersion read rejection: " + code)


def _check(*, runtime, license_guard, project, port, scope, token,
           expected, reader_token=None):
    outline = previous._ids(port, project, scope)[0][0]
    service = _service(runtime, license_guard)
    query = OutlineVersionReadQuery(token, uuid.uuid4(), project, outline)
    page = service.list(query, page_size=1)
    assert len(page.items) == 1 and page.items[0].version_no == expected
    assert page.has_more is (expected > 1)
    for item in page.items:
        assert item.reference_refs[0].scope == scope
        assert service.get(query, item.solution_outline_version_id) == item
    if expected > 1:
        assert page.next_before_version_no == expected
        older = service.list(query, page_size=1,
                             before_version_no=page.next_before_version_no)
        assert len(older.items) == 1 and older.items[0].version_no == 1
        assert older.has_more is False
    if reader_token is not None:
        member = OutlineVersionReadQuery(reader_token, uuid.uuid4(), project, outline)
        assert service.get(member, page.items[0].solution_outline_version_id) == page.items[0]
    _reject("RESOURCE_NOT_FOUND", lambda: service.list(
        OutlineVersionReadQuery(token, uuid.uuid4(), uuid.uuid4(), outline)))
    _reject("AUTH_ACCESS_DENIED", lambda: service.get(
        OutlineVersionReadQuery(b"x" * 32, uuid.uuid4(), project, outline),
        page.items[0].solution_outline_version_id))
    _reject("LICENSE_OPERATION_DENIED", lambda: _service(
        runtime, DeniedLicense()).list(query))


def project_created(**kwargs):
    previous.project_created(**kwargs)
    _check(runtime=kwargs["runtime"], license_guard=kwargs["license_guard"],
           project=kwargs["project"], port=kwargs["port"], scope="PROJECT",
           token=kwargs["token"], reader_token=kwargs["member_token"], expected=2)
    return 0


def global_qualified(**kwargs):
    previous.global_qualified(**kwargs)
    _check(runtime=kwargs["runtime"], license_guard=kwargs["license_guard"],
           project=previous._global_project(kwargs["port"]),
           port=kwargs["port"], scope="GLOBAL", token=b"y" * 32, expected=1)
    return 0


if __name__ == "__main__":
    previous.previous.fixture.main(on_created=project_created)
    previous.previous.composition.global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A05_A02_P02_OUTLINE_VERSION_READ_OWNER_PG_PASS: "
          "PROJECT/GLOBAL fixed history, member, cross-project/Auth/License refusal")
