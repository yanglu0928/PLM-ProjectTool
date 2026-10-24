"""Windows 11 isolated PostgreSQL proof for atomic SolutionOutline CREATE."""

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
from plm_assistant.modules.solution.application.create_outline import (
    CreateOutline, OutlineCreateError, OutlineCreateService,
)
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_project_reference_fixture",
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
    except OutlineCreateError as error:
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
               member_token: bytes, member_csrf: bytes, **_unused) -> int:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.downgrade(cfg, "20261009_0145")
    command.upgrade(cfg, "head")
    command.check(cfg)
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    dependencies = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=authorization, repository=SqlAlchemyOutlineCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(),
    )
    service = OutlineCreateService(**dependencies, audit=audit)
    cmd = CreateOutline(token, csrf, uuid.uuid4(), project, "Synthetic outline", "o" * 16)
    rejects("AUTH_ACCESS_DENIED", lambda: service.create(replace(cmd, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, project_id=other_project)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, session_token=b"u" * 32, csrf_token=b"v" * 32)))
    denied = OutlineCreateService(**{**dependencies, "license_guard": DeniedLicense()}, audit=audit)
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    first = service.create(cmd)
    assert first.outline_state == "ACTIVE" and first.current_approved_version_ref is None
    assert first.etag == '"v0"'
    assert service.create(replace(cmd, trace_id=uuid.uuid4())) == first
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(cmd, name="Changed")))

    member_cmd = CreateOutline(member_token, member_csrf, uuid.uuid4(), project,
                               "Member outline", "m" * 16)
    member_view = service.create(member_cmd)
    assert member_view.solution_outline_id != first.solution_outline_id
    failed = OutlineCreateService(**dependencies, audit=BrokenAudit())
    rejects("SOLUTION_UNAVAILABLE", lambda: failed.create(replace(
        cmd, idempotency_key="f" * 16)))
    parallel = replace(cmd, idempotency_key="p" * 16, name="Concurrent outline")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.create, (parallel, parallel)))
    assert results[0] == results[1]

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_outlines").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.sol_outline_create_results").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='SOL_OUTLINE_CREATED'").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                          "operation='V1_SOL_OUTLINE_CREATE'").fetchone()[0] == 3
        db_rejects("Solution identity operation is not installed", lambda: db.execute(
            "UPDATE plm.sol_outlines SET name='Tampered' WHERE solution_outline_id=%s",
            (first.solution_outline_id,)))
        db_rejects("Solution identity operation is not installed", lambda: db.execute(
            "DELETE FROM plm.sol_outline_create_results WHERE solution_outline_id=%s",
            (first.solution_outline_id,)))
        db_rejects("Solution identity operation is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_sections(project_id,solution_outline_id,section_key,created_by) "
            "VALUES (%s,%s,'overview',%s)", (project, first.solution_outline_id, _unused["manager"])))
        db_rejects("SolutionOutline initial state is invalid", lambda: db.execute(
            "INSERT INTO plm.sol_outlines(project_id,name,outline_state,created_by) "
            "VALUES (%s,'Invalid','ARCHIVED',%s)", (project, _unused["manager"])))
        db_rejects("SolutionOutline create result is required", lambda: db.execute(
            "INSERT INTO plm.sol_outlines(project_id,name,created_by) "
            "VALUES (%s,'No result',%s)", (project, _unused["manager"])))
        db_rejects("Solution identity history cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.sol_outline_create_results"))
        db.execute("ALTER TABLE plm.sol_outlines DISABLE TRIGGER trg_sol_outlines__owner")
        try:
            db.execute("UPDATE plm.sol_outlines SET name='Later metadata' "
                       "WHERE solution_outline_id=%s", (first.solution_outline_id,))
        finally:
            db.execute("ALTER TABLE plm.sol_outlines ENABLE TRIGGER trg_sol_outlines__owner")
    assert service.create(cmd) == first
    try:
        command.downgrade(cfg, "20261009_0145")
    except Exception as error:
        assert "SolutionOutline history prevents Owner downgrade" in str(error), str(error)
    else:
        raise AssertionError("nonempty SolutionOutline downgrade accepted")
    return 0


if __name__ == "__main__":
    prior.main(on_created=on_created)
    print("SOL_02_A03_OUTLINE_CREATE_OWNER_PG_PASS: real Auth/Project, replay, "
          "parallel key, rollback, immutable snapshot, guards, downgrade")
