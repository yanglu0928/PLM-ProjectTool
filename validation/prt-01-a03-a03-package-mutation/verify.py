"""Windows 11/PostgreSQL 18 proof for PrototypePackage mutations."""

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
    PatchPrototypePackage, PrototypePackageMutationError,
    PrototypePackageMutationService, SetPrototypePackageMembers,
)
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import (
    SqlAlchemyPrototypeIdentityCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.package_mutation_repository import (
    SqlAlchemyPrototypePackageMutationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
PREVIOUS = "20261008_0123"


def expect(code: str, action) -> None:
    try:
        action()
    except PrototypePackageMutationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "prt01a03a03_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            pm = seed_user(db, "Prototype mutation PM", "NONE", pm_token)
            impl = seed_user(db, "Prototype mutation IM", "NONE", impl_token)
            customer = seed_user(db, "Prototype mutation Customer", "NONE", customer_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTM01','prtm01','Prototype mutation',%s) RETURNING project_id", (pm,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                "VALUES (%s,'BUS','bus','Business') RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in ((pm,"PROJECT_MANAGER"),(impl,"IMPLEMENTATION_MEMBER"),(customer,"CUSTOMER_MANAGER")):
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
            pm_token, CSRF, uuid.uuid4(), project, "Prototype scope", str(uuid.uuid4()),
        ))
        prototypes = [
            creator.create_prototype(CreatePrototypeIdentity(
                pm_token, CSRF, uuid.uuid4(), project, name, str(uuid.uuid4()),
            )) for name in ("Flow A", "Flow B")
        ]

        def service(audit=None):
            return PrototypePackageMutationService(
                **base, repository=SqlAlchemyPrototypePackageMutationRepository(),
                audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        def patch(version, name, *, token=pm_token, csrf=CSRF, target=None):
            return (target or service()).patch(PatchPrototypePackage(
                token, csrf, uuid.uuid4(), project,
                package.prototype_package_id, version, name,
            ))

        def set_members(version, members, *, key=None, token=pm_token, target=None):
            return (target or service()).set_members(SetPrototypePackageMembers(
                token, CSRF, uuid.uuid4(), project, package.prototype_package_id,
                version, tuple(members), key or str(uuid.uuid4()),
            ))

        expect("RESOURCE_NOT_FOUND", lambda: patch(0, "Denied", token=customer_token))
        expect("AUTH_ACCESS_DENIED", lambda: service().patch(PatchPrototypePackage(
            pm_token, b"x"*32, uuid.uuid4(), project, package.prototype_package_id, 0, "Denied",
        )))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: patch(0, "Denied"))
        guard.enabled = True

        patched = patch(0, "Delivery prototypes")
        assert patched.etag == '"v1"' and patched.member_refs == ()
        expect("CONFLICT_VERSION", lambda: patch(0, "Stale"))

        set_key = str(uuid.uuid4())
        selected = tuple(item.prototype_id for item in prototypes)
        assigned = set_members(1, reversed(selected), key=set_key, token=impl_token)
        assert assigned.etag == '"v2"' and assigned.member_refs == tuple(sorted(selected, key=str))
        assert set_members(1, reversed(selected), key=set_key, token=impl_token) == assigned
        expect("CONFLICT_IDEMPOTENCY", lambda: set_members(1, selected[:1], key=set_key, token=impl_token))
        expect("CONFLICT_NO_CHANGE", lambda: set_members(2, selected))
        emptied = set_members(2, ())
        assert emptied.etag == '"v3"' and emptied.member_refs == ()

        expect(
            "PROTOTYPE_UNAVAILABLE",
            lambda: patch(3, "Audit rollback", target=service(FailedAudit())),
        )
        recovered = patch(3, "Recovered name")
        assert recovered.etag == '"v4"'

        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.prt_prototypes").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM plm.prt_package_memberships").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM plm.prt_package_command_results").fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_PRT_PACKAGE_SET_MEMBERS'"
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_PRT_PACKAGE_PATCH'"
            ).fetchone()[0] == 0
            try:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.prt_package_memberships(prototype_package_id,prototype_id,project_id,added_by) "
                        "VALUES (%s,%s,%s,%s)",
                        (package.prototype_package_id, selected[0], project, pm),
                    )
            except Exception as error:
                assert "PrototypePackage mutation has no immutable result" in str(error), str(error)
            else:
                raise AssertionError("unclosed membership committed")
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (impl,))
        expect("AUTH_ACCESS_DENIED", lambda: set_members(1, reversed(selected), key=set_key, token=impl_token))
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "PrototypePackage mutation history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0124 accepted mutation history")
        print(
            "PRT_01_A03_A03_PACKAGE_MUTATION_PASS: PATCH without receipt, atomic "
            "SET_MEMBERS/replay, roles, License, Audit rollback, membership closure "
            "and history refusal verified on PostgreSQL 18"
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
