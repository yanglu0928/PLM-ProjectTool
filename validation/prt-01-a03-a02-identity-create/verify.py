"""Windows 11/PostgreSQL 18 proof for Prototype identity creation."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
from plm_assistant.modules.prototype.application.create_identity import (
    CreatePrototypeIdentity, CreatePrototypePackage, PrototypeIdentityCreateError,
    PrototypeIdentityCreateService,
)
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import (
    SqlAlchemyPrototypeIdentityCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
PREVIOUS = "20261008_0122"


def expect(code: str, action) -> None:
    try:
        action()
    except PrototypeIdentityCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "prt01a03a02_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            pm = seed_user(db, "Prototype PM", "NONE", pm_token)
            impl = seed_user(db, "Prototype Implementer", "NONE", impl_token)
            customer = seed_user(db, "Prototype Customer", "NONE", customer_token)
            project = db.execute(
                """INSERT INTO plm.prj_projects(
                     project_code,project_code_normalized,name,created_by)
                   VALUES ('PRTC01','prtc01','Prototype Project',%s)
                   RETURNING project_id""", (pm,),
            ).fetchone()[0]
            department = db.execute(
                """INSERT INTO plm.prj_departments(
                     project_id,department_code,department_code_normalized,name)
                   VALUES (%s,'BUS','bus','Business') RETURNING department_id""",
                (project,),
            ).fetchone()[0]
            for actor, role in (
                (pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    """INSERT INTO plm.prj_project_members(
                         project_id,user_id,department_id,project_role)
                       VALUES (%s,%s,%s,%s)""",
                    (project, actor, department, role),
                )

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        common = dict(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemyPrototypeIdentityCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )

        def service(audit=None):
            return PrototypeIdentityCreateService(
                **common, audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        def create_package(*, token=pm_token, csrf=CSRF, name="Prototype scope", key=None, target=None):
            return (target or service()).create_package(CreatePrototypePackage(
                token, csrf, uuid.uuid4(), project, name, key or str(uuid.uuid4()),
            ))

        def create_prototype(*, token=pm_token, csrf=CSRF, name="Approval flow", key=None, target=None):
            return (target or service()).create_prototype(CreatePrototypeIdentity(
                token, csrf, uuid.uuid4(), project, name, key or str(uuid.uuid4()),
            ))

        expect("RESOURCE_NOT_FOUND", lambda: create_package(token=customer_token))
        expect("AUTH_ACCESS_DENIED", lambda: create_prototype(csrf=b"x" * 32))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", create_package)
        guard.enabled = True

        package_key = str(uuid.uuid4())
        package = create_package(key=package_key)
        assert create_package(key=package_key) == package
        assert create_package(token=impl_token, name="Implementation package").project_id == project

        prototype_key = str(uuid.uuid4())
        prototype = create_prototype(key=prototype_key)
        assert create_prototype(key=prototype_key) == prototype
        expect(
            "CONFLICT_IDEMPOTENCY",
            lambda: create_prototype(key=prototype_key, name="Different flow"),
        )

        failed_key = str(uuid.uuid4())
        expect(
            "PROTOTYPE_UNAVAILABLE",
            lambda: create_prototype(
                key=failed_key, name="Rollback flow", target=service(FailedAudit()),
            ),
        )
        recovered = create_prototype(key=failed_key, name="Rollback flow")
        assert recovered.prototype_id != prototype.prototype_id

        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.prt_packages").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.prt_prototypes").fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action IN "
                "('PROTOTYPE_PACKAGE_CREATED','PROTOTYPE_CREATED')"
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation IN "
                "('V1_PRT_PACKAGE_CREATE','V1_PRT_CREATE')"
            ).fetchone()[0] == 4
            try:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.prt_prototypes(project_id,name,created_by) "
                        "VALUES (%s,'Unclosed direct root',%s)", (project, pm),
                    )
            except Exception as error:
                assert "Prototype has no immutable create result" in str(error), str(error)
            else:
                raise AssertionError("unclosed Prototype root committed")
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (pm,))
        expect("AUTH_ACCESS_DENIED", lambda: create_prototype(key=prototype_key))
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Prototype create result history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0123 accepted create result history")
        print(
            "PRT_01_A03_A02_IDENTITY_CREATE_PASS: Session/CSRF, roles, License, "
            "package/prototype create, immutable replay, conflict, Audit rollback, "
            "root closure and history refusal verified on PostgreSQL 18"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
