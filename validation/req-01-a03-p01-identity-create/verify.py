"""Windows 11/PostgreSQL 18 proof for Requirement identity creation."""

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
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity,
    CreateRequirementPackage,
    RequirementIdentityCreateError,
    RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import (
    SqlAlchemyRequirementIdentityCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py")
)
connect = helpers["connect"]
seed_user = helpers["seed_user"]
Guard = helpers["Guard"]
FailedAudit = helpers["FailedAudit"]
CSRF = helpers["CSRF"]
PREVIOUS = "20261007_0111"


def expect(code: str, action) -> None:
    try:
        action()
    except RequirementIdentityCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def reject_db(expected: str, action) -> None:
    try:
        action()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + expected)


def main() -> None:
    database = "req01a03p01_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg",
            username="poc_admin",
            host="127.0.0.1",
            port=55434,
            database=database,
        )
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
                    """
                    INSERT INTO plm.prj_projects(
                      project_code,project_code_normalized,name,created_by)
                    VALUES ('REQP01','reqp01','Requirement Project',%s)
                    RETURNING project_id
                    """,
                    (pm,),
                ).fetchone()[0]
                department = db.execute(
                    """
                    INSERT INTO plm.prj_departments(
                      project_id,department_code,department_code_normalized,name)
                    VALUES (%s,'BUS','bus','Business') RETURNING department_id
                    """,
                    (project,),
                ).fetchone()[0]
                for actor, role in (
                    (pm, "PROJECT_MANAGER"),
                    (impl, "IMPLEMENTATION_MEMBER"),
                    (customer, "CUSTOMER_MANAGER"),
                ):
                    db.execute(
                        """
                        INSERT INTO plm.prj_project_members(
                          project_id,user_id,department_id,project_role)
                        VALUES (%s,%s,%s,%s)
                        """,
                        (project, actor, department, role),
                    )

            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            )
            common = dict(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(),
                license_guard=guard,
                authorization=authorization,
                repository=SqlAlchemyRequirementIdentityCreateRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                clock=lambda: datetime.now(timezone.utc),
            )

            def service(audit=None):
                return RequirementIdentityCreateService(
                    **common,
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                )

            def create_package(
                *, token=pm_token, csrf=CSRF, name="Implementation scope", key=None,
                target=None,
            ):
                return (target or service()).create_package(
                    CreateRequirementPackage(
                        token,
                        csrf,
                        uuid.uuid4(),
                        project,
                        name,
                        key or str(uuid.uuid4()),
                    )
                )

            def create_requirement(
                *, token=pm_token, csrf=CSRF, code="REQ-001", key=None,
                target=None,
            ):
                return (target or service()).create_requirement(
                    CreateRequirementIdentity(
                        token,
                        csrf,
                        uuid.uuid4(),
                        project,
                        code,
                        key or str(uuid.uuid4()),
                    )
                )

            expect("RESOURCE_NOT_FOUND", lambda: create_package(token=customer_token))
            expect("AUTH_ACCESS_DENIED", lambda: create_package(csrf=b"x" * 32))
            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", create_package)
            guard.enabled = True

            package_key = str(uuid.uuid4())
            package = create_package(key=package_key)
            assert create_package(key=package_key) == package
            implementation_package = create_package(
                token=impl_token, name="Implementation owned scope"
            )
            assert implementation_package.project_id == project

            requirement_key = str(uuid.uuid4())
            requirement = create_requirement(key=requirement_key)
            assert create_requirement(key=requirement_key) == requirement
            expect(
                "CONFLICT_IDEMPOTENCY",
                lambda: create_requirement(key=requirement_key, code="REQ-002"),
            )
            expect("CONFLICT_DUPLICATE", lambda: create_requirement(code="req-001"))

            concurrent_key = str(uuid.uuid4())
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(
                        lambda _: create_requirement(
                            key=concurrent_key, code="REQ-CONCURRENT"
                        ),
                        range(2),
                    )
                )
            assert results[0] == results[1]

            failed_key = str(uuid.uuid4())
            failed = service(FailedAudit())
            expect(
                "REQUIREMENT_UNAVAILABLE",
                lambda: create_requirement(
                    key=failed_key, code="REQ-ROLLBACK", target=failed
                ),
            )
            recovered = create_requirement(key=failed_key, code="REQ-ROLLBACK")
            assert recovered.requirement_id not in {
                requirement.requirement_id,
                results[0].requirement_id,
            }

            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.req_packages"
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirements"
                ).fetchone()[0] == 3
                assert db.execute(
                    "SELECT count(*) FROM plm.req_package_create_results"
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirement_create_results"
                ).fetchone()[0] == 3
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE "
                    "action IN ('REQUIREMENT_PACKAGE_CREATED','REQUIREMENT_CREATED')"
                ).fetchone()[0] == 5
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                    "operation IN ('V1_REQ_PACKAGE_CREATE','V1_REQ_CREATE')"
                ).fetchone()[0] == 5
                forged_package = uuid.uuid4()

                def forge_result() -> None:
                    with db.transaction():
                        created_at = db.execute(
                            """
                            INSERT INTO plm.req_packages(
                              requirement_package_id,project_id,name,created_by)
                            VALUES (%s,%s,'Original',%s) RETURNING created_at
                            """,
                            (forged_package, project, pm),
                        ).fetchone()[0]
                        db.execute(
                            """
                            INSERT INTO plm.req_package_create_results(
                              requirement_package_id,project_id,name,created_at)
                            VALUES (%s,%s,'Forged',%s)
                            """,
                            (forged_package, project, created_at),
                        )

                reject_db(
                    "Requirement create result does not match initial identity",
                    forge_result,
                )
                db.execute(
                    "UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (pm,)
                )
            expect(
                "AUTH_ACCESS_DENIED", lambda: create_requirement(key=requirement_key)
            )
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "Requirement create result history prevents downgrade" in str(
                    error
                ), str(error)
            else:
                raise AssertionError("Schema0112 accepted create result history")
            print(
                "REQ_01_A03_P01_IDENTITY_CREATE_PASS: Session/CSRF, PM and "
                "Implementation roles, License, package/requirement create, immutable "
                "replay, conflict, concurrency, Audit rollback and history refusal "
                "verified on PostgreSQL 18"
            )
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )


if __name__ == "__main__":
    main()
