"""Win11 disposable PG18 proof of atomic SolutionSection identity CREATE."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.create_section import (
    CreateSection, SectionCreateError, SectionCreateService,
)
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture", ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


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
    except SectionCreateError as error:
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
               other_project: uuid.UUID, manager: uuid.UUID, member: uuid.UUID,
               token: bytes, csrf: bytes, member_token: bytes, member_csrf: bytes,
               **_unused) -> int:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.downgrade(cfg, "20261009_0147")
    command.upgrade(cfg, "head")
    command.check(cfg)
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    common = dict(unit_of_work=runtime.unit_of_work,
                  access=SqlAlchemyProjectWriteAccess(),
                  license_guard=license_guard, authorization=authorization,
                  receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    outline = OutlineCreateService(**common, repository=SqlAlchemyOutlineCreateRepository()).create(
        CreateOutline(token, csrf, uuid.uuid4(), project, "Sections parent", "outline-parent-0001"))
    dependencies = dict(**common, repository=SqlAlchemySectionCreateRepository())
    service = SectionCreateService(**dependencies)
    cmd = CreateSection(token, csrf, uuid.uuid4(), project,
                        outline.solution_outline_id, " Overview ", "section-create-0001")
    rejects("VALIDATION_FAILED", lambda: service.create(replace(cmd, section_key="\u0000")))
    rejects("AUTH_ACCESS_DENIED", lambda: service.create(replace(cmd, csrf_token=b"x" * 32)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(cmd, project_id=other_project)))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(cmd, outline_id=uuid.uuid4())))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, session_token=b"u" * 32, csrf_token=b"v" * 32)))
    denied = SectionCreateService(**{**dependencies, "license_guard": DeniedLicense()})
    rejects("LICENSE_OPERATION_DENIED", lambda: denied.create(cmd))
    first = service.create(cmd)
    assert first.section_key == "Overview" and first.section_state == "ACTIVE"
    assert first.current_approved_version_ref is None and first.etag == '"v0"'
    assert service.create(replace(cmd, trace_id=uuid.uuid4())) == first
    rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(cmd, section_key="Other")))
    rejects("CONFLICT_DUPLICATE", lambda: service.create(replace(
        cmd, idempotency_key="section-duplicate-0001", section_key="Overview")))

    member_cmd = CreateSection(member_token, member_csrf, uuid.uuid4(), project,
                               outline.solution_outline_id, "Details", "section-member-0001")
    member_view = service.create(member_cmd)
    assert member_view.solution_section_id != first.solution_section_id
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 "
                   "WHERE user_id=%s AND project_id=%s", (member, project))
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        member_cmd, idempotency_key="section-paused-0001")))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 "
                   "WHERE user_id=%s AND project_id=%s", (member, project))
        db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 "
                   "WHERE project_id=%s", (project,))
    rejects("PROJECT_ARCHIVED", lambda: service.create(replace(
        cmd, idempotency_key="section-archived-project-0001", section_key="Archived project")))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("UPDATE plm.prj_projects SET state='ACTIVE',lock_version=lock_version+1 "
                   "WHERE project_id=%s", (project,))
        db.execute("ALTER TABLE plm.sol_outlines DISABLE TRIGGER trg_sol_outlines__owner")
        try:
            db.execute("UPDATE plm.sol_outlines SET outline_state='ARCHIVED',lock_version=lock_version+1 "
                       "WHERE solution_outline_id=%s", (outline.solution_outline_id,))
        finally:
            db.execute("ALTER TABLE plm.sol_outlines ENABLE TRIGGER trg_sol_outlines__owner")
    rejects("RESOURCE_NOT_FOUND", lambda: service.create(replace(
        cmd, idempotency_key="section-archived-outline-0001", section_key="Archived outline")))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_outlines DISABLE TRIGGER trg_sol_outlines__owner")
        try:
            db.execute("UPDATE plm.sol_outlines SET outline_state='ACTIVE',lock_version=lock_version+1 "
                       "WHERE solution_outline_id=%s", (outline.solution_outline_id,))
        finally:
            db.execute("ALTER TABLE plm.sol_outlines ENABLE TRIGGER trg_sol_outlines__owner")

    failed = SectionCreateService(**{**dependencies, "audit": BrokenAudit()})
    rejects("SOLUTION_UNAVAILABLE", lambda: failed.create(replace(
        cmd, idempotency_key="section-audit-fail-0001", section_key="Rollback")))
    parallel = replace(cmd, idempotency_key="section-parallel-0001", section_key="Concurrent")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.create, (parallel, parallel)))
    assert results[0] == results[1]

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_sections").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.sol_section_create_results").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='SOL_SECTION_CREATED'").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                          "operation='V1_SOL_SECTION_CREATE'").fetchone()[0] == 3
        db_rejects("Solution identity operation is not installed", lambda: db.execute(
            "UPDATE plm.sol_sections SET section_key='Tampered' WHERE solution_section_id=%s",
            (first.solution_section_id,)))
        db_rejects("Solution identity operation is not installed", lambda: db.execute(
            "DELETE FROM plm.sol_section_create_results WHERE solution_section_id=%s",
            (first.solution_section_id,)))
        db_rejects("SolutionSection initial state is invalid", lambda: db.execute(
            "INSERT INTO plm.sol_sections(project_id,solution_outline_id,section_key,"
            "section_state,created_by) VALUES (%s,%s,'Invalid','ARCHIVED',%s)",
            (project, outline.solution_outline_id, manager)))
        db_rejects("SolutionSection create result is required", lambda: db.execute(
            "INSERT INTO plm.sol_sections(project_id,solution_outline_id,section_key,created_by) "
            "VALUES (%s,%s,'No result',%s)", (project, outline.solution_outline_id, manager)))
        db_rejects("SolutionSection first result does not match root", lambda: db.execute(
            "INSERT INTO plm.sol_section_create_results(solution_section_id,solution_outline_id,"
            "project_id,section_key,created_at) VALUES (%s,%s,%s,'Mismatch',%s)",
            (first.solution_section_id, outline.solution_outline_id, project, first.created_at)))
        db_rejects("Solution identity history cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.sol_section_create_results"))
        db_rejects("SolutionSectionVersion Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_section_versions(solution_section_id,project_id,version_no,"
            "title,content_artifact_ref,content_fingerprint,assumptions,exclusions,"
            "declared_requirement_count,declared_evidence_count,created_by) "
            "VALUES (%s,%s,1,'Closed',%s,%s,'[]'::jsonb,'[]'::jsonb,0,0,%s)",
            (first.solution_section_id, project, uuid.uuid4(), b"0" * 32, manager)))
        db.execute("ALTER TABLE plm.sol_sections DISABLE TRIGGER trg_sol_sections__owner")
        try:
            db.execute("UPDATE plm.sol_sections SET section_key='Later metadata' "
                       "WHERE solution_section_id=%s", (first.solution_section_id,))
        finally:
            db.execute("ALTER TABLE plm.sol_sections ENABLE TRIGGER trg_sol_sections__owner")
    assert service.create(cmd) == first
    try:
        command.downgrade(cfg, "20261009_0147")
    except Exception as error:
        assert "SolutionSection history prevents Owner downgrade" in str(error), str(error)
    else:
        raise AssertionError("nonempty SolutionSection downgrade accepted")
    return 0


if __name__ == "__main__":
    fixture.main(on_created=on_created)
    print("SOL_04_A03_SECTION_CREATE_OWNER_PASS: real Session/PG, role, "
          "atomic Receipt/Audit, same-key concurrency, closure and rollback")
