"""Windows 11 isolated PostgreSQL proof for atomic internal PLAN_CREATE."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.plan.application.create_plan import (
    CreatePlan, PlanCreateError, PlanCreateService,
)
from plm_assistant.modules.plan.infrastructure.create_repository import SqlAlchemyPlanCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_project_reference_fixture_for_plan",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class BrokenAudit:
    def append(self, tx, event):
        raise RuntimeError("synthetic Audit rollback")


class DeniedLicense:
    def require_valid(self, *, trace_id):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def rejects(code: str, action) -> None:
    try:
        action()
    except PlanCreateError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def db_rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def on_created(*, port: int, runtime, audit, license_guard, project: uuid.UUID,
               other_project: uuid.UUID, token: bytes, csrf: bytes,
               member_token: bytes, member_csrf: bytes, **context) -> int:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.downgrade(cfg, "20261019_0168")
    command.upgrade(cfg, "head")
    command.check(cfg)
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=authorization, repository=SqlAlchemyPlanCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(),
    )
    service = PlanCreateService(**dependencies, audit=audit)
    cmd = CreatePlan(token, csrf, uuid.uuid4(), project, "Synthetic plan", "p" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.create(replace(cmd, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, project_id=other_project)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, session_token=b"u" * 32, csrf_token=b"v" * 32)))
    denied = PlanCreateService(**{**dependencies, "license_guard": DeniedLicense()}, audit=audit)
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    first = service.create(cmd)
    assert first.plan_state == "ACTIVE" and first.current_approved_version_ref is None
    assert first.etag == '"v0"'
    assert service.create(replace(cmd, trace_id=uuid.uuid4())) == first
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(cmd, name="Changed")))

    member_cmd = CreatePlan(member_token, member_csrf, uuid.uuid4(), project,
                            "Member plan", "m" * 16)
    member_view = service.create(member_cmd)
    assert member_view.plan_id != first.plan_id
    failed = PlanCreateService(**dependencies, audit=BrokenAudit())
    rejects("PLAN_UNAVAILABLE", lambda: failed.create(replace(
        cmd, idempotency_key="f" * 16)))
    parallel = replace(cmd, idempotency_key="q" * 16, name="Concurrent plan")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.create, (parallel, parallel)))
    assert results[0] == results[1]

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.pln_plans").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.pln_plan_create_results").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='PLAN_CREATED'").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                          "operation='V1_PLAN_CREATE'").fetchone()[0] == 3
        db_rejects("Plan identity operation is not installed", lambda: db.execute(
            "UPDATE plm.pln_plans SET name='Tampered' WHERE plan_id=%s", (first.plan_id,)))
        db_rejects("Plan create result operation is not installed", lambda: db.execute(
            "DELETE FROM plm.pln_plan_create_results WHERE plan_id=%s", (first.plan_id,)))
        db_rejects("Plan initial state is invalid", lambda: db.execute(
            "INSERT INTO plm.pln_plans(project_id,name,plan_state,created_by) "
            "VALUES (%s,'Invalid','ARCHIVED',%s)", (project, context["manager"])))
        db_rejects("Plan create result is required", lambda: db.execute(
            "INSERT INTO plm.pln_plans(project_id,name,created_by) "
            "VALUES (%s,'No result',%s)", (project, context["manager"])))
        db_rejects("Plan create result history cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.pln_plan_create_results"))
        db.execute("ALTER TABLE plm.pln_plans DISABLE TRIGGER trg_pln_plans__owner")
        try:
            db.execute("UPDATE plm.pln_plans SET name='Later metadata' "
                       "WHERE plan_id=%s", (first.plan_id,))
        finally:
            db.execute("ALTER TABLE plm.pln_plans ENABLE TRIGGER trg_pln_plans__owner")
    assert service.create(cmd) == first
    try:
        command.downgrade(cfg, "20261019_0168")
    except Exception as error:
        assert "Plan history prevents create Owner downgrade" in str(error), str(error)
    else:
        raise AssertionError("nonempty Plan Owner downgrade accepted")
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("PLAN_01_A03_P02_CREATE_OWNER_PG_PASS: real Auth/Project, replay, "
          "parallel key, rollback, immutable snapshot, guards and downgrade")
