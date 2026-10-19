"""Windows 11 real Auth/Project/PG proof for current Plan identity reads."""

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
from plm_assistant.modules.plan.application.create_plan import CreatePlan, PlanCreateService
from plm_assistant.modules.plan.application.read_plan import PlanReadError, PlanReadQuery, PlanReadService
from plm_assistant.modules.plan.infrastructure.create_repository import SqlAlchemyPlanCreateRepository
from plm_assistant.modules.plan.infrastructure.read_repository import SqlAlchemyPlanReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_project_reference_fixture_for_plan_read",
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
    except PlanReadError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def on_created(*, port, runtime, audit, license_guard, project,
               other_project, manager, member, token, csrf,
               member_token, **_unused):
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    creator = PlanCreateService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyPlanCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    created = creator.create(CreatePlan(
        token, csrf, uuid.uuid4(), project, "Read target", "r" * 16))
    next_plan = creator.create(CreatePlan(
        token, csrf, uuid.uuid4(), project, "Another plan", "n" * 16))
    reader = PlanReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard, authorization=authorization,
        repository=SqlAlchemyPlanReadRepository())
    query = PlanReadQuery(token, uuid.uuid4(), project)
    view = reader.get_current(query, created.plan_id)
    assert view.plan_id == created.plan_id and view.name == "Read target"
    assert view.plan_state == "ACTIVE" and view.current_approved_version_ref is None
    assert view.etag == '"v0"' and view.created_by == manager
    member_query = PlanReadQuery(member_token, uuid.uuid4(), project)
    assert reader.get_current(member_query, created.plan_id) == view
    page1 = reader.list_current(query, limit=1)
    page2 = reader.list_current(query, limit=1, after_plan_id=page1.next_after_plan_id)
    assert len(page1.items) == len(page2.items) == 1
    assert page1.has_more and not page2.has_more
    assert {page1.items[0].plan_id, page2.items[0].plan_id} == {
        created.plan_id, next_plan.plan_id}
    assert len(reader.list_current(member_query).items) == 2
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        PlanReadQuery(token, uuid.uuid4(), other_project), created.plan_id))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.list_current(
        PlanReadQuery(token, uuid.uuid4(), other_project)))
    rejects("AUTH_ACCESS_DENIED", lambda: reader.get_current(
        PlanReadQuery(secrets.token_bytes(32), uuid.uuid4(), project), created.plan_id))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get_current(query, uuid.uuid4()))
    denied = PlanReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=DeniedLicense(), authorization=authorization,
        repository=SqlAlchemyPlanReadRepository())
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.list_current(query))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        before = db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                            "target_owner_module='plan'").fetchone()[0]
        assert before == 2
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                   "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                   (member, project))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.get_current(
        member_query, created.plan_id))
    rejects("RESOURCE_NOT_FOUND", lambda: reader.list_current(member_query))
    assert reader.get_current(query, created.plan_id) == view
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "target_owner_module='plan'").fetchone()[0] == before
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("PLAN_01_A03_P03_READ_OWNER_PG_PASS: real PG/Session, current member, "
          "bounded pages, isolation, revocation, License and zero read Audit")
