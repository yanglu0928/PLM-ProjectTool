"""Win11 isolated PG proof for SolutionOutline detail read owner."""

from __future__ import annotations

import importlib.util
import secrets
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.read_outline import OutlineReadError, OutlineReadQuery, OutlineReadService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("EXPIRED")


def rejects(code, action):
    try:
        action()
    except OutlineReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, runtime, audit, license_guard, project,
               other_project, manager, member, token, csrf,
               member_token, **_unused):
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    creator = OutlineCreateService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyOutlineCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    created = creator.create(CreateOutline(
        token, csrf, uuid.uuid4(), project, "Read target", "r" * 16))
    reader = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyOutlineReadRepository())
    query = OutlineReadQuery(token, uuid.uuid4(), project)
    view = reader.get_current(query, created.solution_outline_id)
    assert view.solution_outline_id == created.solution_outline_id
    assert view.name == "Read target" and view.outline_state == "ACTIVE"
    assert view.current_approved_version_ref is None and view.etag == '"v0"'
    assert view.created_by == manager
    member_view = reader.get_current(
        OutlineReadQuery(member_token, uuid.uuid4(), project),
        created.solution_outline_id)
    assert member_view == view
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        OutlineReadQuery(token, uuid.uuid4(), other_project),
        created.solution_outline_id))
    rejects("AUTH_ACCESS_DENIED", lambda: reader.get_current(
        OutlineReadQuery(secrets.token_bytes(32), uuid.uuid4(), project),
        created.solution_outline_id))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        query, uuid.uuid4()))
    denied = OutlineReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=DeniedLicense(), authorization=authorization,
        repository=SqlAlchemyOutlineReadRepository())
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.get_current(
        query, created.solution_outline_id))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        OutlineReadQuery(member_token, uuid.uuid4(), project),
        created.solution_outline_id))
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("SOL_02_A06_P01_OUTLINE_READ_OWNER_PASS: real PG/Session, "
          "member, project isolation, License and empty approved pointer")
