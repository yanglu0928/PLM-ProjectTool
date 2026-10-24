"""Windows 11/PostgreSQL 18 proof for Requirement Package mutations."""

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
    CreateRequirementIdentity, CreateRequirementPackage, RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.mutate_package import (
    ChangeRequirementPackageMembers, PatchRequirementPackage,
    RequirementPackageMutationError, RequirementPackageMutationService,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.package_mutation_repository import SqlAlchemyRequirementPackageMutationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
PREVIOUS = "20261007_0112"


def expect(code: str, action) -> None:
    try:
        action()
    except RequirementPackageMutationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "req01a03p02_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    other_pm_token = b"o" * 32
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
                other_pm = seed_user(db, "Other Requirement PM", "NONE", other_pm_token)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQP02','reqp02','Requirement Project',%s) RETURNING project_id", (pm,)
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQP02B','reqp02b','Other Project',%s) RETURNING project_id", (pm,)
                ).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)
                ).fetchone()[0]
                other_department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (other_project,)
                ).fetchone()[0]
                for actor, role in ((pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                                    (customer, "CUSTOMER_MANAGER")):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                               "VALUES (%s,%s,%s,%s)", (project, actor, department, role))
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                           "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                           (other_project, other_pm, other_department))

            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            )
            base = dict(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                        authorization=authorization, receipts=SqlAlchemyIdempotencyReceipts(),
                        clock=lambda: datetime.now(timezone.utc))
            audit = AuditService(SqlAlchemyAuditRepository())
            creator = RequirementIdentityCreateService(
                **base, repository=SqlAlchemyRequirementIdentityCreateRepository(), audit=audit,
            )
            mutation = RequirementPackageMutationService(
                **base, repository=SqlAlchemyRequirementPackageMutationRepository(), audit=audit,
            )

            package = creator.create_package(CreateRequirementPackage(
                pm_token, CSRF, uuid.uuid4(), project, "Implementation scope", str(uuid.uuid4())
            ))
            requirements = [creator.create_requirement(CreateRequirementIdentity(
                pm_token, CSRF, uuid.uuid4(), project, f"REQ-{number:03d}", str(uuid.uuid4())
            )) for number in range(1, 5)]
            foreign = creator.create_requirement(CreateRequirementIdentity(
                other_pm_token, CSRF, uuid.uuid4(), other_project, "REQ-FOREIGN", str(uuid.uuid4())
            ))

            def patch(*, version=0, token=pm_token, csrf=CSRF,
                      name="Delivery scope", state=None, target=mutation):
                return target.patch(PatchRequirementPackage(
                    token, csrf, uuid.uuid4(), project, package.requirement_package_id,
                    version, name=name, package_state=state,
                ))

            def change(method, *, ids, version, key=None, token=pm_token, target=mutation):
                return method(ChangeRequirementPackageMembers(
                    token, CSRF, uuid.uuid4(), project, package.requirement_package_id,
                    version, tuple(ids), key or str(uuid.uuid4()),
                ))

            expect("RESOURCE_NOT_FOUND", lambda: patch(token=customer_token))
            expect("AUTH_ACCESS_DENIED", lambda: patch(csrf=b"x" * 32))
            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", patch)
            guard.enabled = True

            with connect(database) as db:
                receipts_before_patch = db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts"
                ).fetchone()[0]
            patched = patch()
            assert patched.etag == '"v1"'
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts"
                ).fetchone()[0] == receipts_before_patch

            add_key = str(uuid.uuid4())
            added = change(mutation.add_members, ids=[requirements[1].requirement_id,
                           requirements[0].requirement_id], version=1, key=add_key,
                           token=impl_token)
            assert added.etag == '"v2"' and len(added.member_refs) == 2
            assert change(mutation.add_members, ids=[requirements[0].requirement_id,
                          requirements[1].requirement_id], version=1, key=add_key,
                          token=impl_token) == added
            expect("CONFLICT_DUPLICATE", lambda: change(
                mutation.add_members, ids=[requirements[0].requirement_id], version=2
            ))
            expect("RESOURCE_NOT_FOUND", lambda: change(
                mutation.add_members, ids=[foreign.requirement_id], version=2
            ))

            remove_key = str(uuid.uuid4())
            removed = change(mutation.remove_members, ids=[requirements[0].requirement_id],
                             version=2, key=remove_key)
            assert removed.etag == '"v3"' and removed.member_refs == (requirements[1].requirement_id,)
            assert change(mutation.add_members, ids=[requirements[0].requirement_id,
                          requirements[1].requirement_id], version=1, key=add_key,
                          token=impl_token) == added
            expect("CONFLICT_VERSION", lambda: patch(version=2, name="Stale"))

            def race(item):
                try:
                    return change(mutation.add_members, ids=[item], version=3)
                except RequirementPackageMutationError as error:
                    return error.code
            with ThreadPoolExecutor(max_workers=2) as pool:
                raced = list(pool.map(race, [requirements[2].requirement_id,
                                             requirements[3].requirement_id]))
            assert sum(value == "CONFLICT_VERSION" for value in raced) == 1, raced
            winner = next(value for value in raced if value != "CONFLICT_VERSION")
            current_version = int(winner.etag[2:-1])

            failed = RequirementPackageMutationService(
                **base, repository=SqlAlchemyRequirementPackageMutationRepository(),
                audit=FailedAudit(),
            )
            expect("REQUIREMENT_UNAVAILABLE", lambda: patch(
                version=current_version, name="Rollback", target=failed
            ))
            recovered = patch(version=current_version, name="Recovered")
            assert recovered.name == "Recovered"

            with connect(database) as db:
                assert db.execute("SELECT count(*) FROM plm.req_requirements WHERE project_id=%s",
                                  (project,)).fetchone()[0] == 4
                assert db.execute("SELECT count(*) FROM plm.req_package_command_results").fetchone()[0] == 5
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action IN ("
                                  "'REQUIREMENT_PACKAGE_PATCHED',"
                                  "'REQUIREMENT_PACKAGE_REQUIREMENTS_ADDED',"
                                  "'REQUIREMENT_PACKAGE_REQUIREMENTS_REMOVED')").fetchone()[0] == 5
                try:
                    with db.transaction():
                        db.execute("INSERT INTO plm.req_package_command_results("
                                   "result_id,requirement_package_id,project_id,operation,name,"
                                   "package_state,member_refs,lock_version) VALUES ("
                                   "%s,%s,%s,'PATCH','Forged','ACTIVE',ARRAY[]::uuid[],999)",
                                   (uuid.uuid4(), package.requirement_package_id, project))
                except psycopg.Error as error:
                    assert "does not match current root" in str(error), str(error)
                else:
                    raise AssertionError("forged command snapshot accepted")
                db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (pm,))
            expect("AUTH_ACCESS_DENIED", patch)
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "mutation history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("Schema0113 accepted mutation history")
            print("REQ_01_A03_P02_PACKAGE_MUTATION_PASS: authorization, License, non-idempotent patch, "
                  "membership add/remove without Requirement deletion, canonical replay, "
                  "optimistic concurrency, Audit rollback, forged snapshot rejection and "
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
