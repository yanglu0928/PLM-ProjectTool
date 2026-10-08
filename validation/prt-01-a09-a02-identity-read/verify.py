"""Windows 11/PostgreSQL 18 proof for Prototype identity reads."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.prototype.application.read_identities import (
    PrototypeIdentityReadError, PrototypeIdentityReadQuery,
    PrototypeIdentityReadService,
)
from plm_assistant.modules.prototype.infrastructure.identity_read_repository import (
    SqlAlchemyPrototypeIdentityReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_user, Guard = (
    helpers["connect"], helpers["seed_user"], helpers["Guard"])
definition = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
seed_dependencies = definition["seed_dependencies"]


def main() -> None:
    database = "prt01a09a02_" + uuid.uuid4().hex[:8]
    token = b"r" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head"); command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            actor = seed_user(db, "Prototype reader", "NONE", token)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')",
                       (ids["project"], actor, ids["department"]))
            packages = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
            prototypes = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
            base = datetime.now(timezone.utc).replace(microsecond=123456)
            # Synthetic read projection only: bypass write-owner closure while
            # preserving the real tables, indexes and authorization path.
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for ordinal, identity in enumerate(packages):
                    at = base - timedelta(minutes=ordinal)
                    db.execute("INSERT INTO plm.prt_packages(prototype_package_id,project_id,name,package_state,created_by,created_at,updated_at,lock_version) VALUES (%s,%s,%s,'ACTIVE',%s,%s,%s,%s)",
                               (identity, ids["project"], f"Package {ordinal}", actor, at, at, ordinal))
                for ordinal, identity in enumerate(prototypes):
                    at = base - timedelta(minutes=ordinal)
                    state = "ARCHIVED" if ordinal == 2 else "ACTIVE"
                    db.execute("INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,prototype_state,current_approved_version_ref,created_by,created_at,updated_at,lock_version) VALUES (%s,%s,%s,%s,NULL,%s,%s,%s,%s)",
                               (identity, ids["project"], f"Prototype {ordinal}", state, actor, at, at, ordinal))
                for prototype in sorted(
                        prototypes[:2], key=lambda value: value.bytes):
                    db.execute("INSERT INTO plm.prt_package_memberships(prototype_package_id,prototype_id,project_id,added_by) VALUES (%s,%s,%s,%s)",
                               (packages[0], prototype, ids["project"], actor))

        runtime = create_database_runtime(url)
        service = PrototypeIdentityReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=Guard(),
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            repository=SqlAlchemyPrototypeIdentityReadRepository(),
        )
        query = PrototypeIdentityReadQuery(token, uuid.uuid4(), ids["project"])
        first = service.list_packages(query, page_size=2)
        second = service.list_packages(
            query, page_size=2, after_updated_at=first.next_updated_at,
            after_prototype_package_id=first.next_prototype_package_id,
        )
        assert tuple(item.prototype_package_id for item in first.items) == packages[:2]
        assert tuple(item.prototype_package_id for item in second.items) == packages[2:]
        package = service.get_package(query, packages[0])
        assert package.prototype_ids == tuple(sorted(
            prototypes[:2], key=lambda value: value.bytes))
        assert package.summary.etag == '"v0"'

        prototype_page = service.list_prototypes(query, page_size=2)
        assert tuple(item.prototype_id for item in prototype_page.items) == prototypes[:2]
        prototype = service.get_prototype(query, prototypes[2])
        assert (prototype.prototype_state, prototype.etag) == ("ARCHIVED", '"v2"')

        try:
            service.get_prototype(
                PrototypeIdentityReadQuery(token, uuid.uuid4(), uuid.uuid4()),
                prototypes[0],
            )
        except PrototypeIdentityReadError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else:
            raise AssertionError("wrong project disclosed Prototype")

        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_id=%s AND user_id=%s",
                           (ids["project"], actor))
        try: service.list_prototypes(query, page_size=10)
        except PrototypeIdentityReadError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else: raise AssertionError("suspended member retained read access")
        command.check(cfg)
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("PRT_01_A09_A02_IDENTITY_READ_PASS: authorized package/prototype list/get, stable pagination, membership projection, ETag, project isolation and live revocation verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
