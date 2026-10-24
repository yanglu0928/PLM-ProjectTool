"""Windows 11/PostgreSQL 18 proof for Requirement identity reads."""

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
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, CreateRequirementPackage,
    RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.mutate_package import (
    ChangeRequirementPackageMembers, RequirementPackageMutationService,
)
from plm_assistant.modules.requirement.application.read_identities import (
    RequirementIdentityReadError, RequirementIdentityReadQuery,
    RequirementIdentityReadService,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.identity_read_repository import SqlAlchemyRequirementIdentityReadRepository
from plm_assistant.modules.requirement.infrastructure.package_mutation_repository import SqlAlchemyRequirementPackageMutationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]


def expect(code, action):
    try:
        action()
    except RequirementIdentityReadError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "req01a10a02_" + uuid.uuid4().hex[:8]
    tokens = {"pm": b"p" * 32, "impl": b"i" * 32, "customer": b"c" * 32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        try:
            with connect(database) as db:
                actors = {
                    name: seed_user(db, "Identity Read " + name, "NONE", token)
                    for name, token in tokens.items()
                }
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQIR01','reqir01','Identity Read Project',%s) RETURNING project_id",
                    (actors["pm"],)).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQIR02','reqir02','Other Project',%s) RETURNING project_id",
                    (actors["pm"],)).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)).fetchone()[0]
                for name, role in (
                    ("pm", "PROJECT_MANAGER"),
                    ("impl", "IMPLEMENTATION_MEMBER"),
                    ("customer", "CUSTOMER_MEMBER"),
                ):
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,%s)",
                        (project, actors[name], department, role))

            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository())
            common = dict(
                unit_of_work=runtime.unit_of_work, license_guard=guard,
                authorization=authorization,
                clock=lambda: datetime.now(timezone.utc))
            audit = AuditService(SqlAlchemyAuditRepository())
            creator = RequirementIdentityCreateService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                repository=SqlAlchemyRequirementIdentityCreateRepository(),
                audit=audit)
            packages = [
                creator.create_package(CreateRequirementPackage(
                    tokens["pm"], CSRF, uuid.uuid4(), project, name,
                    str(uuid.uuid4())))
                for name in ("Primary Scope", "Secondary Scope")
            ]
            requirements = [
                creator.create_requirement(CreateRequirementIdentity(
                    tokens["impl"], CSRF, uuid.uuid4(), project, code,
                    str(uuid.uuid4())))
                for code in ("REQ-IR-001", "REQ-IR-002", "REQ-IR-003")
            ]
            mutation = RequirementPackageMutationService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                repository=SqlAlchemyRequirementPackageMutationRepository(),
                audit=audit)
            mutated = mutation.add_members(ChangeRequirementPackageMembers(
                tokens["pm"], CSRF, uuid.uuid4(), project,
                packages[0].requirement_package_id, 0,
                (requirements[1].requirement_id, requirements[0].requirement_id),
                str(uuid.uuid4())))
            assert mutated.etag == '"v1"'

            reads = RequirementIdentityReadService(
                **common, access=SqlAlchemyProjectReadAccess(),
                repository=SqlAlchemyRequirementIdentityReadRepository())

            def query(name="customer", project_id=project, token=None):
                return RequirementIdentityReadQuery(
                    token or tokens[name], uuid.uuid4(), project_id)

            with connect(database) as db:
                before = db.execute(
                    "SELECT (SELECT count(*) FROM plm.aud_events),"
                    "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                    "(SELECT count(*) FROM plm.req_packages),"
                    "(SELECT count(*) FROM plm.req_requirements)").fetchone()

            package_page_1 = reads.list_packages(query(), page_size=1)
            assert package_page_1.has_more
            assert package_page_1.next_updated_at is not None
            assert package_page_1.next_requirement_package_id is not None
            package_page_2 = reads.list_packages(
                query("pm"), page_size=1,
                after_updated_at=package_page_1.next_updated_at,
                after_requirement_package_id=package_page_1.next_requirement_package_id)
            assert not package_page_2.has_more
            assert len({package_page_1.items[0].requirement_package_id,
                        package_page_2.items[0].requirement_package_id}) == 2

            requirement_page_1 = reads.list_requirements(query(), page_size=2)
            assert requirement_page_1.has_more
            requirement_page_2 = reads.list_requirements(
                query("impl"), page_size=2,
                after_updated_at=requirement_page_1.next_updated_at,
                after_requirement_id=requirement_page_1.next_requirement_id)
            assert not requirement_page_2.has_more
            assert len({item.requirement_id for item in requirement_page_1.items
                        + requirement_page_2.items}) == 3

            package = reads.get_package(
                query(), packages[0].requirement_package_id)
            expected_members = tuple(sorted(
                (requirements[0].requirement_id, requirements[1].requirement_id),
                key=lambda value: value.bytes))
            assert package.requirement_ids == expected_members
            assert package.summary.etag == '"v1"'
            requirement = reads.get_requirement(
                query("impl"), requirements[0].requirement_id)
            assert requirement.requirement_code == "REQ-IR-001"
            assert requirement.requirement_state == "ACTIVE"
            assert requirement.current_approved_version_ref is None
            assert requirement.etag == '"v0"'

            expect("RESOURCE_NOT_FOUND", lambda: reads.get_requirement(
                query(project_id=other), requirements[0].requirement_id))
            expect("AUTH_ACCESS_DENIED", lambda: reads.list_packages(
                query(token=b"x" * 32), page_size=10))
            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", lambda: reads.list_requirements(
                query(), page_size=10))
            guard.enabled = True

            with connect(database) as db:
                after = db.execute(
                    "SELECT (SELECT count(*) FROM plm.aud_events),"
                    "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                    "(SELECT count(*) FROM plm.req_packages),"
                    "(SELECT count(*) FROM plm.req_requirements)").fetchone()
            assert after == before, (before, after)
            command.check(cfg)
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "REQ_01_A10_A02_IDENTITY_READ_PASS: member package/requirement list/get, "
        "paired keysets, ordered membership, isolation, denials, zero writes and "
        "drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
