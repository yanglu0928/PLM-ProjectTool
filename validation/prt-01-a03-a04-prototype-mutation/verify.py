"""Windows 11/PostgreSQL 18 proof for Prototype identity mutations."""

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
    CreatePrototypeIdentity, CreatePrototypePackage, PrototypeIdentityCreateService,
)
from plm_assistant.modules.prototype.application.mutate_package import (
    PrototypePackageMutationService, SetPrototypePackageMembers,
)
from plm_assistant.modules.prototype.application.mutate_prototype import (
    ArchivePrototypeIdentity, PatchPrototypeIdentity, PrototypeMutationError,
    PrototypeMutationService,
)
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import (
    SqlAlchemyPrototypeIdentityCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.package_mutation_repository import (
    SqlAlchemyPrototypePackageMutationRepository,
)
from plm_assistant.modules.prototype.infrastructure.prototype_mutation_repository import (
    SqlAlchemyPrototypeMutationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
PREVIOUS = "20261008_0124"


def expect(code: str, action) -> None:
    try:
        action()
    except PrototypeMutationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "prt01a03a04_" + uuid.uuid4().hex[:8]
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
            pm = seed_user(db, "Prototype identity PM", "NONE", pm_token)
            impl = seed_user(db, "Prototype identity IM", "NONE", impl_token)
            customer = seed_user(db, "Prototype identity Customer", "NONE", customer_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTM02','prtm02','Prototype identity mutation',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                "VALUES (%s,'BUS','bus','Business') RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in (
                (pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,%s)", (project, actor, department, role),
                )

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        base = dict(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )
        creator = PrototypeIdentityCreateService(
            **base, repository=SqlAlchemyPrototypeIdentityCreateRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        package = creator.create_package(CreatePrototypePackage(
            pm_token, CSRF, uuid.uuid4(), project, "Archive retention", str(uuid.uuid4()),
        ))
        prototype = creator.create_prototype(CreatePrototypeIdentity(
            pm_token, CSRF, uuid.uuid4(), project, "Flow A", str(uuid.uuid4()),
        ))
        closure_probe = creator.create_prototype(CreatePrototypeIdentity(
            pm_token, CSRF, uuid.uuid4(), project, "Closure probe", str(uuid.uuid4()),
        ))
        package_service = PrototypePackageMutationService(
            **base, repository=SqlAlchemyPrototypePackageMutationRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        package_service.set_members(SetPrototypePackageMembers(
            pm_token, CSRF, uuid.uuid4(), project, package.prototype_package_id,
            0, (prototype.prototype_id,), str(uuid.uuid4()),
        ))

        def service(audit=None):
            return PrototypeMutationService(
                **base, repository=SqlAlchemyPrototypeMutationRepository(),
                audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        def patch(version, name, *, token=pm_token, csrf=CSRF, target=None):
            return (target or service()).patch(PatchPrototypeIdentity(
                token, csrf, uuid.uuid4(), project, prototype.prototype_id, version, name,
            ))

        def archive(version, *, key=None, token=pm_token, target=None):
            return (target or service()).archive(ArchivePrototypeIdentity(
                token, CSRF, uuid.uuid4(), project, prototype.prototype_id,
                version, key or str(uuid.uuid4()),
            ))

        expect("RESOURCE_NOT_FOUND", lambda: patch(0, "Denied", token=customer_token))
        expect("AUTH_ACCESS_DENIED", lambda: patch(0, "Denied", csrf=b"x" * 32))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: patch(0, "Denied"))
        guard.enabled = True

        expect(
            "PROTOTYPE_UNAVAILABLE",
            lambda: patch(0, "Audit rollback", target=service(FailedAudit())),
        )
        patched = patch(0, "Flow A confirmed", token=impl_token)
        assert patched.etag == '"v1"' and patched.prototype_state == "ACTIVE"
        expect("CONFLICT_VERSION", lambda: patch(0, "Stale"))
        expect("CONFLICT_NO_CHANGE", lambda: patch(1, "Flow A confirmed"))
        expect("RESOURCE_NOT_FOUND", lambda: archive(1, token=impl_token))

        archive_key = str(uuid.uuid4())
        archived = archive(1, key=archive_key)
        assert archived.etag == '"v2"' and archived.prototype_state == "ARCHIVED"
        assert archive(1, key=archive_key) == archived
        expect("CONFLICT_IDEMPOTENCY", lambda: archive(0, key=archive_key))
        expect("PROTOTYPE_STATE_INVALID", lambda: archive(2))
        expect("PROTOTYPE_STATE_INVALID", lambda: patch(2, "No rewrite"))

        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.prt_package_memberships WHERE prototype_id=%s",
                (prototype.prototype_id,),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.prt_prototype_command_results"
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_PRT_ARCHIVE'"
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_PRT_PATCH'"
            ).fetchone()[0] == 0
            try:
                with db.transaction():
                    db.execute(
                        "UPDATE plm.prt_prototypes SET name='Unclosed', updated_by=%s, "
                        "updated_at=statement_timestamp(), lock_version=lock_version+1 "
                        "WHERE prototype_id=%s",
                        (pm, closure_probe.prototype_id),
                    )
            except Exception as error:
                assert "Prototype mutation has no immutable result" in str(error), str(error)
            else:
                raise AssertionError("unclosed Prototype mutation committed")
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (pm,))
        expect("AUTH_ACCESS_DENIED", lambda: archive(1, key=archive_key))
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Prototype mutation history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0125 accepted Prototype mutation history")
        print(
            "PRT_01_A03_A04_PROTOTYPE_MUTATION_PASS: PATCH without receipt, one-way "
            "ARCHIVE/replay, roles, License, Audit rollback, membership retention, "
            "root/result closure and history refusal verified on PostgreSQL 18"
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
