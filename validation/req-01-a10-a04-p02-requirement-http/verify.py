"""Windows 11/PostgreSQL 18 proof for Requirement identity HTTP."""

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
from plm_assistant.modules.requirement.api.requirement_cursor import RequirementCursorCodec
from plm_assistant.modules.requirement.api.requirements import create_requirement_router
from plm_assistant.modules.requirement.application.create_identity import RequirementIdentityCreateService
from plm_assistant.modules.requirement.application.mutate_requirement import RequirementMutationService
from plm_assistant.modules.requirement.application.read_identities import RequirementIdentityReadService
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.identity_read_repository import SqlAlchemyRequirementIdentityReadRepository
from plm_assistant.modules.requirement.infrastructure.requirement_mutation_repository import SqlAlchemyRequirementMutationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
evidence_helpers = runpy.run_path(
    str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))
seed_evidence = evidence_helpers["seed_evidence"]
TOKENS = {
    "pm": b"p" * 32, "impl": b"i" * 32,
    "customer": b"c" * 32, "reader": b"r" * 32,
}


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token not in TOKENS.values() or require_csrf and csrf_token != CSRF):
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
    database = "req01a10a04p02_" + uuid.uuid4().hex[:8]
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
                    name: seed_user(db, "Requirement HTTP " + name, "NONE", token)
                    for name, token in TOKENS.items()
                }
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQHTTP2','reqhttp2','Requirement HTTP Project',%s) RETURNING project_id",
                    (actors["pm"],)).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)).fetchone()[0]
                for name, role in (
                    ("pm", "PROJECT_MANAGER"),
                    ("impl", "IMPLEMENTATION_MEMBER"),
                    ("customer", "CUSTOMER_MANAGER"),
                    ("reader", "CUSTOMER_MEMBER"),
                ):
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,%s)",
                        (project, actors[name], department, role))
                evidence = seed_evidence(db, project, actors["pm"])

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
            mutations = RequirementMutationService(
                **common, access=SqlAlchemyProjectWriteAccess(),
                repository=SqlAlchemyRequirementMutationRepository(),
                receipts=receipts, audit=audit)
            reads = RequirementIdentityReadService(
                **common, access=SqlAlchemyProjectReadAccess(),
                repository=SqlAlchemyRequirementIdentityReadRepository())
            router = create_requirement_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                reads=reads, creates=creates, mutations=mutations,
                cursors=RequirementCursorCodec(b"q" * 32))
            app = create_app(requirement_router=router)
            root = f"/api/v1/projects/{project}/requirements"

            with TestClient(app, base_url="https://plm.example.test") as client:
                created = {}
                for name, code in (
                    ("patch", "REQ-HTTP-PATCH"),
                    ("defer", "REQ-HTTP-DEFER"),
                    ("reject", "REQ-HTTP-REJECT"),
                    ("archive", "REQ-HTTP-ARCHIVE"),
                ):
                    created[name] = expect(client.post(
                        root, headers=headers("impl", key=str(uuid.uuid4())),
                        json={"requirement_code": code}), 201)

                page_one = expect(client.get(
                    root + "?page_size=1", headers=headers("reader")), 200)
                assert page_one["has_more"] and page_one["next_cursor"]
                page_two = expect(client.get(
                    root + "?page_size=1&cursor=" + page_one["next_cursor"],
                    headers=headers("reader")), 200)
                assert page_two["items"] and page_two["items"][0]["requirement_id"] \
                    != page_one["items"][0]["requirement_id"]

                patch_path = root + "/" + created["patch"]["requirement_id"]
                detail = expect(client.get(
                    patch_path, headers=headers("reader")), 200)
                assert detail["etag"] == '"v0"' and detail["state"] == "ACTIVE"

                with connect(database) as db:
                    receipts_before_patch = db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts").fetchone()[0]
                patched = expect(client.patch(
                    patch_path, headers=headers("impl", etag='"v0"'),
                    json={"requirement_code": "REQ-HTTP-PATCHED"}), 200)
                assert patched["etag"] == '"v1"'
                with connect(database) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts"
                    ).fetchone()[0] == receipts_before_patch
                assert client.patch(
                    patch_path, headers=headers("impl", etag='"v0"'),
                    json={"requirement_code": "REQ-HTTP-STALE"}).status_code == 409

                decision = {
                    "reason": "Customer decision",
                    "impact": "Schedule and scope impact",
                    "evidence_ids": [str(evidence)],
                }
                defer_path = root + "/" + created["defer"]["requirement_id"] + ":defer"
                defer_key = str(uuid.uuid4())
                deferred = expect(client.post(
                    defer_path, headers=headers(
                        "customer", key=defer_key, etag='"v0"'),
                    json=decision), 200)
                replayed = expect(client.post(
                    defer_path, headers=headers(
                        "customer", key=defer_key, etag='"v0"'),
                    json=decision), 200)
                assert replayed == deferred and deferred["state"] == "DEFERRED"
                assert deferred["decision_ref"] and deferred["evidence_refs"] == [str(evidence)]

                reject_path = root + "/" + created["reject"]["requirement_id"] + ":reject"
                rejected = expect(client.post(
                    reject_path, headers=headers(
                        "customer", key=str(uuid.uuid4()), etag='"v0"'),
                    json=decision), 200)
                assert rejected["state"] == "REJECTED" and rejected["decision_ref"]

                archive_path = root + "/" + created["archive"]["requirement_id"] + ":archive"
                archived = expect(client.post(
                    archive_path, headers=headers(
                        "pm", key=str(uuid.uuid4()), etag='"v0"')), 200)
                assert archived["state"] == "ARCHIVED" and archived["decision_ref"] is None

                denied = client.patch(
                    patch_path, headers=headers("reader", etag='"v1"'),
                    json={"requirement_code": "REQ-DENIED"})
                assert denied.status_code == 404
                guard.enabled = False
                assert client.get(root, headers=headers("reader")).status_code == 403
                guard.enabled = True

            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirements").fetchone()[0] == 4
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirement_state_decisions"
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirement_decision_evidence_refs"
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.req_requirement_command_results"
                ).fetchone()[0] == 4
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE action IN ("
                    "'REQUIREMENT_PATCHED','REQUIREMENT_DEFERRED',"
                    "'REQUIREMENT_REJECTED','REQUIREMENT_ARCHIVED')"
                ).fetchone()[0] == 4
            command.check(cfg)
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "REQ_01_A10_A04_P02_REQUIREMENT_HTTP_PASS: seven frozen HTTP operations, "
        "dedicated cursor, ETag, PATCH zero-receipt, decision Evidence, state replay, "
        "denials, Audit and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
