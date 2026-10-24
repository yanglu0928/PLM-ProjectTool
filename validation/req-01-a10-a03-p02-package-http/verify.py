"""Windows 11/PostgreSQL 18 proof for RequirementPackage HTTP."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.api.package_cursor import RequirementPackageCursorCodec
from plm_assistant.modules.requirement.api.packages import create_requirement_package_router
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.mutate_package import RequirementPackageMutationService
from plm_assistant.modules.requirement.application.read_identities import RequirementIdentityReadService
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.identity_read_repository import SqlAlchemyRequirementIdentityReadRepository
from plm_assistant.modules.requirement.infrastructure.package_mutation_repository import SqlAlchemyRequirementPackageMutationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
TOKENS = {"pm": b"p" * 32, "customer": b"c" * 32}


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token not in TOKENS.values()
                or require_csrf and csrf_token != CSRF):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers(name="pm", *, key=None, etag=None):
    result = {
        "origin": "https://plm.example.test",
        "cookie": "plm_session=" + TOKENS[name].hex(),
        "x-csrf-token": CSRF.hex(),
    }
    if key is not None:
        result["idempotency-key"] = key
    if etag is not None:
        result["if-match"] = etag
    return result


def expect(response, status):
    if response.status_code != status:
        raise AssertionError((response.status_code, response.text))
    return response.json()["data"]


def main() -> None:
    database = "req01a10a03p02_" + uuid.uuid4().hex[:8]
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
                    name: seed_user(db, "Package HTTP " + name, "NONE", token)
                    for name, token in TOKENS.items()
                }
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQHTTP1','reqhttp1','Package HTTP Project',%s) RETURNING project_id",
                    (actors["pm"],)).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)).fetchone()[0]
                for name, role in (
                    ("pm", "PROJECT_MANAGER"),
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
            receipts = SqlAlchemyIdempotencyReceipts()
            creates = RequirementIdentityCreateService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                repository=SqlAlchemyRequirementIdentityCreateRepository(),
                receipts=receipts, audit=audit)
            mutations = RequirementPackageMutationService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                repository=SqlAlchemyRequirementPackageMutationRepository(),
                receipts=receipts, audit=audit)
            reads = RequirementIdentityReadService(
                **common, access=SqlAlchemyProjectReadAccess(),
                repository=SqlAlchemyRequirementIdentityReadRepository())
            router = create_requirement_package_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                reads=reads, creates=creates, mutations=mutations,
                cursors=RequirementPackageCursorCodec(b"k" * 32))
            app = create_app(requirement_package_router=router)
            root = f"/api/v1/projects/{project}/requirement-packages"

            with TestClient(app, base_url="https://plm.example.test") as client:
                first = expect(client.post(
                    root, headers=headers(key=str(uuid.uuid4())),
                    json={"name": "Primary scope"}), 201)
                second = expect(client.post(
                    root, headers=headers(key=str(uuid.uuid4())),
                    json={"name": "Secondary scope"}), 201)
                package_id = first["requirement_package_id"]

                requirements = [creates.create_requirement(CreateRequirementIdentity(
                    TOKENS["pm"], CSRF, uuid.uuid4(), project, code,
                    str(uuid.uuid4()))) for code in ("REQ-HTTP-001", "REQ-HTTP-002")]

                page_one = expect(client.get(
                    root + "?page_size=1", headers=headers("customer")), 200)
                assert page_one["has_more"] and page_one["next_cursor"]
                page_two = expect(client.get(
                    root + "?page_size=1&cursor=" + page_one["next_cursor"],
                    headers=headers("customer")), 200)
                assert not page_two["has_more"]
                assert {page_one["items"][0]["requirement_package_id"],
                        page_two["items"][0]["requirement_package_id"]} == {
                            package_id, second["requirement_package_id"]}

                detail_path = root + "/" + package_id
                detail = expect(client.get(
                    detail_path, headers=headers("customer")), 200)
                assert detail["etag"] == '"v0"' and detail["requirement_ids"] == []

                with connect(database) as db:
                    receipts_before_patch = db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts").fetchone()[0]
                patched = expect(client.patch(
                    detail_path, headers=headers(etag='"v0"'),
                    json={"name": "Updated scope"}), 200)
                assert patched["etag"] == '"v1"'
                with connect(database) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts"
                    ).fetchone()[0] == receipts_before_patch

                member_ids = [str(value.requirement_id) for value in requirements]
                add_key = str(uuid.uuid4())
                added = expect(client.post(
                    detail_path + ":add-requirements",
                    headers=headers(key=add_key, etag='"v1"'),
                    json={"requirement_ids": list(reversed(member_ids))}), 200)
                replayed = expect(client.post(
                    detail_path + ":add-requirements",
                    headers=headers(key=add_key, etag='"v1"'),
                    json={"requirement_ids": list(reversed(member_ids))}), 200)
                assert replayed == added and added["etag"] == '"v2"'

                removed = expect(client.post(
                    detail_path + ":remove-requirements",
                    headers=headers(key=str(uuid.uuid4()), etag='"v2"'),
                    json={"requirement_ids": [member_ids[0]]}), 200)
                assert removed["etag"] == '"v3"' and removed["requirement_ids"] == [member_ids[1]]

                denied = client.post(
                    root, headers=headers("customer", key=str(uuid.uuid4())),
                    json={"name": "Denied"})
                assert denied.status_code == 404
                guard.enabled = False
                assert client.get(root, headers=headers("customer")).status_code == 403
                guard.enabled = True

            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.req_packages").fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.req_package_memberships"
                ).fetchone()[0] == 1
                assert db.execute(
                    "SELECT count(*) FROM plm.req_package_command_results"
                ).fetchone()[0] == 3
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE action IN ("
                    "'REQUIREMENT_PACKAGE_PATCHED',"
                    "'REQUIREMENT_PACKAGE_REQUIREMENTS_ADDED',"
                    "'REQUIREMENT_PACKAGE_REQUIREMENTS_REMOVED')"
                ).fetchone()[0] == 3
            command.check(cfg)
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "REQ_01_A10_A03_P02_PACKAGE_HTTP_PASS: six frozen HTTP operations, "
        "dedicated cursor, member reads, ETag, PATCH zero-receipt, command replay, "
        "denials, Audit and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
