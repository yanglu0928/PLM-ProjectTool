"""Windows 11/PostgreSQL 18 proof for Requirement identity mutations."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.mutate_requirement import (
    ArchiveRequirementIdentity, DecideRequirementIdentity, PatchRequirementIdentity,
    RequirementMutationError, RequirementMutationService,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.requirement_mutation_repository import SqlAlchemyRequirementMutationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
evidence_helpers = runpy.run_path(str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))
seed_evidence = evidence_helpers["seed_evidence"]
PREVIOUS = "20261007_0114"


def expect(code: str, action) -> None:
    try:
        action()
    except RequirementMutationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "req01a03p03p02_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p"*32, b"i"*32, b"c"*32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        try:
            with connect(database) as db:
                pm = seed_user(db, "Requirement PM", "NONE", pm_token)
                impl = seed_user(db, "Requirement Implementer", "NONE", impl_token)
                customer = seed_user(db, "Requirement Customer", "NONE", customer_token)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQM01','reqm01','Requirement Mutation Project',%s) RETURNING project_id",
                    (pm,)).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQM02','reqm02','Other Project',%s) RETURNING project_id",
                    (pm,)).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)).fetchone()[0]
                for actor, role in ((pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                                    (customer, "CUSTOMER_MANAGER")):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                               "VALUES (%s,%s,%s,%s)", (project, actor, department, role))
                evidence = seed_evidence(db, project, pm)
                evidence2 = seed_evidence(db, project, pm)
                foreign_evidence = seed_evidence(db, other_project, pm)
                global_evidence = seed_evidence(db, None, pm)
                revoked_evidence = seed_evidence(db, project, pm)
                db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                           "eligibility_reason='Revoked fixture',updated_by=%s,lock_version=lock_version+1 "
                           "WHERE evidence_id=%s", (pm, revoked_evidence))

            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository())
            base = dict(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                        authorization=authorization, receipts=SqlAlchemyIdempotencyReceipts(),
                        clock=lambda: datetime.now(timezone.utc))
            audit = AuditService(SqlAlchemyAuditRepository())
            creator = RequirementIdentityCreateService(
                **base, repository=SqlAlchemyRequirementIdentityCreateRepository(), audit=audit)
            mutation = RequirementMutationService(
                **base, repository=SqlAlchemyRequirementMutationRepository(), audit=audit)

            def create(code):
                return creator.create_requirement(CreateRequirementIdentity(
                    pm_token, CSRF, uuid.uuid4(), project, code, str(uuid.uuid4())))
            roots = {name: create(code) for name, code in (
                ("patch", "REQ-PATCH"), ("defer", "REQ-DEFER"),
                ("reject", "REQ-REJECT"), ("archive", "REQ-ARCHIVE"),
                ("race", "REQ-RACE"), ("rollback", "REQ-ROLLBACK"),
                ("duplicate", "REQ-DUPLICATE"), ("direct", "REQ-DIRECT"))}

            def patch(root, *, version=0, code="REQ-PATCHED",
                      token=impl_token, csrf=CSRF, target=mutation):
                return target.patch(PatchRequirementIdentity(
                    token, csrf, uuid.uuid4(), project, root.requirement_id,
                    version, code))

            def decide(method, root, *, version=0, ids=(evidence,), key=None,
                       token=customer_token, target=mutation):
                return method(DecideRequirementIdentity(
                    token, CSRF, uuid.uuid4(), project, root.requirement_id, version,
                    "Customer decision", "Schedule and scope impact", tuple(ids),
                    key or str(uuid.uuid4())))

            def archive(root, *, version=0, key=None, token=pm_token, target=mutation):
                return target.archive(ArchiveRequirementIdentity(
                    token, CSRF, uuid.uuid4(), project, root.requirement_id,
                    version, key or str(uuid.uuid4())))

            expect("RESOURCE_NOT_FOUND", lambda: patch(roots["patch"], token=customer_token))
            expect("AUTH_ACCESS_DENIED", lambda: patch(roots["patch"], csrf=b"x"*32))
            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", lambda: patch(roots["patch"]))
            guard.enabled = True

            with connect(database) as db:
                receipts_before_patch = db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts"
                ).fetchone()[0]
            patched = patch(roots["patch"])
            assert patched.etag == '"v1"' and patched.requirement_code == "REQ-PATCHED"
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts"
                ).fetchone()[0] == receipts_before_patch
            expect("CONFLICT_DUPLICATE", lambda: patch(
                roots["duplicate"], code="req-patched"))
            expect("RESOURCE_NOT_FOUND", lambda: decide(
                mutation.defer, roots["defer"], token=impl_token))
            for bad in ((foreign_evidence,), (global_evidence,), (revoked_evidence,)):
                expect("REQUIREMENT_DECISION_INVALID", lambda bad=bad: decide(
                    mutation.defer, roots["defer"], ids=bad))

            defer_key = str(uuid.uuid4())
            deferred = decide(mutation.defer, roots["defer"],
                              ids=(evidence2, evidence), key=defer_key)
            assert deferred.requirement_state == "DEFERRED"
            assert deferred.evidence_refs == tuple(sorted((evidence, evidence2), key=str))
            rejected = decide(mutation.reject, roots["reject"])
            assert rejected.requirement_state == "REJECTED"
            expect("RESOURCE_NOT_FOUND", lambda: archive(roots["archive"], token=impl_token))
            archived = archive(roots["archive"])
            assert archived.requirement_state == "ARCHIVED"
            deferred_archived = archive(roots["defer"], version=1)
            assert deferred_archived.requirement_state == "ARCHIVED"
            assert decide(mutation.defer, roots["defer"],
                          ids=(evidence2, evidence), key=defer_key) == deferred
            expect("CONFLICT_VERSION", lambda: patch(roots["patch"], version=0))

            def race(code):
                try:
                    return patch(roots["race"], code=code, token=pm_token)
                except RequirementMutationError as error:
                    return error.code
            with ThreadPoolExecutor(max_workers=2) as pool:
                raced = list(pool.map(race, ("REQ-RACE-A", "REQ-RACE-B")))
            assert sum(value == "CONFLICT_VERSION" for value in raced) == 1, raced

            failed = RequirementMutationService(
                **base, repository=SqlAlchemyRequirementMutationRepository(), audit=FailedAudit())
            expect("REQUIREMENT_UNAVAILABLE", lambda: patch(
                roots["rollback"], code="REQ-FAILED", token=pm_token,
                target=failed))
            recovered = patch(roots["rollback"], code="REQ-RECOVERED", token=pm_token)
            assert recovered.requirement_code == "REQ-RECOVERED"

            with connect(database) as db:
                try:
                    with db.transaction():
                        db.execute("UPDATE plm.req_requirements SET requirement_code='REQ-DIRECT-X',"
                                   "requirement_code_normalized='REQ-DIRECT-X',updated_by=%s,"
                                   "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                                   "WHERE requirement_id=%s", (pm, roots["direct"].requirement_id))
                except psycopg.Error as error:
                    assert "has no immutable result" in str(error), str(error)
                else:
                    raise AssertionError("direct root mutation committed without result")
                try:
                    with db.transaction():
                        db.execute("INSERT INTO plm.req_requirement_command_results("
                                   "result_id,requirement_id,project_id,operation,requirement_code,"
                                   "requirement_state,evidence_refs,lock_version) VALUES ("
                                   "%s,%s,%s,'PATCH','REQ-FORGED','ACTIVE',ARRAY[]::uuid[],999)",
                                   (uuid.uuid4(), roots["patch"].requirement_id, project))
                except psycopg.Error as error:
                    assert "does not match current root" in str(error), str(error)
                else:
                    raise AssertionError("forged result accepted")
                assert db.execute("SELECT count(*) FROM plm.req_requirement_state_decisions").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.req_requirement_decision_evidence_refs").fetchone()[0] == 3
                assert db.execute("SELECT count(*) FROM plm.req_requirement_command_results").fetchone()[0] == 7
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action IN ("
                                  "'REQUIREMENT_PATCHED','REQUIREMENT_DEFERRED',"
                                  "'REQUIREMENT_REJECTED','REQUIREMENT_ARCHIVED')").fetchone()[0] == 7
                db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (impl,))
            expect("AUTH_ACCESS_DENIED", lambda: patch(roots["patch"]))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "Requirement mutation history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("Schema0115 accepted mutation history")
            print("REQ_01_A03_P03_P02_REQUIREMENT_MUTATION_PASS: roles, License, "
                  "non-idempotent PATCH, idempotent DEFER/REJECT evidence proof and ARCHIVE, "
                  "immutable replay, concurrency, Audit rollback, database closure and "
                  "history refusal verified on PostgreSQL 18")
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (database,))
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
