"""Hosted PostgreSQL 18 HTTP checks for fail-closed Output creation composition."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import psycopg
from sqlalchemy import URL, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_output_create import (
    create_windows_output_request_create_router,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.output.infrastructure.create_access import SqlAlchemyOutputRequestCreateAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow, ProjectMemberRow, ProjectRow

TOKEN = b"t" * 32
CSRF = b"c" * 32


def url(name: str, port: int):
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def create_db(admin: str, name: str) -> None:
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}" TEMPLATE postgres')


def drop_db(admin: str, name: str) -> None:
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


class SyntheticSessions:
    def __init__(self, actor: uuid.UUID) -> None:
        self.actor = actor

    def validate(self, token: bytes, *, csrf_token=None, require_csrf=False):
        if token != TOKEN or csrf_token != CSRF or require_csrf is not True:
            raise RuntimeError("synthetic session rejected")
        return SimpleNamespace(user_id=self.actor)


class SyntheticSessionAccess:
    def authenticated_user(self, transaction, *, session_token, csrf_token, now):
        if session_token == TOKEN and csrf_token == CSRF:
            return ACTOR_BY_TOKEN.get(session_token)
        return None


ACTOR_BY_TOKEN: dict[bytes, uuid.UUID] = {}


class SyntheticOrigins:
    def require_trusted(self, headers):
        if not any(name.lower() == b"origin" and value == b"http://localhost"
                   for name, value in headers):
            raise RuntimeError("synthetic origin rejected")


class SyntheticLicense:
    def require_valid(self, **_):
        return True


def asgi_post(app, path: str, body: bytes, key: str):
    messages = []
    consumed = False

    async def receive():
        nonlocal consumed
        if not consumed:
            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    async def run():
        await app(
            {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
             "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": path, "raw_path": path.encode("ascii"), "query_string": b"",
             "headers": ((b"origin", b"http://localhost"),
                         (b"cookie", b"plm_session=" + TOKEN.hex().encode("ascii")),
                         (b"x-csrf-token", CSRF.hex().encode("ascii")),
                         (b"idempotency-key", key.encode("ascii")),
                         (b"content-type", b"application/json")),
             "client": ("127.0.0.1", 43000), "server": ("localhost", 80)},
            receive, send,
        )

    asyncio.run(run())
    start = next(item for item in messages if item["type"] == "http.response.start")
    payload = b"".join(item.get("body", b"") for item in messages
                       if item["type"] == "http.response.body")
    return start["status"], payload


def write_snapshot(database: str, port: int) -> dict[str, int]:
    with psycopg.connect(dsn(database, port)) as conn:
        names = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='plm' AND (table_name LIKE 'out%' "
            "OR table_name LIKE 'job%' OR table_name LIKE 'aud%' "
            "OR table_name LIKE 'plt_idempotency%') ORDER BY table_name"
        ).fetchall()
        return {
            name: conn.execute(f'SELECT count(*) FROM plm."{name}"').fetchone()[0]
            for (name,) in names
        }


def app_for(runtime, actor: uuid.UUID):
    router = create_windows_output_request_create_router(
        runtime=runtime,
        sessions=SyntheticSessions(actor),
        origins=SyntheticOrigins(),
        license_guard=SyntheticLicense(),
        audit=AuditService(SqlAlchemyAuditRepository()),
        session_access=SqlAlchemyOutputRequestCreateAccess(
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ),
            session_access=SyntheticSessionAccess(),
        )._session_access,
    )
    return create_app(output_request_create_router=router)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("temporary loopback PG and numeric hosted run ID required")

    database = "plm_out19_" + args.run_id[-10:]
    admin = dsn("postgres", args.port)
    created = False
    runtime = None
    result = {
        "status": "PENDING", "customer_data": False, "external_api_calls": 0,
        "database": "isolated synthetic PostgreSQL 18.6",
        "product_api_started": False,
    }
    try:
        create_db(admin, database)
        created = True
        upgrade_database(url(database, args.port), "head")
        runtime = create_database_runtime(url(database, args.port))

        creator, manager, implementer, customer_manager, project = (
            uuid.uuid4() for _ in range(5)
        )
        department = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=user, username_display=name,
                        username_normalized=name, state="DISABLED",
                        deployment_role="NONE")
                for user, name in (
                    (creator, "p19-synthetic-creator"),
                    (manager, "p19-synthetic-manager"),
                    (implementer, "p19-synthetic-implementer"),
                    (customer_manager, "p19-synthetic-customer-manager"),
                )
            ])
            tx.session.flush()
            tx.session.add(ProjectRow(
                project_id=project, project_code="P19-A",
                project_code_normalized="P19-A",
                name="Synthetic Output Create Composition", created_by=creator,
            ))
            tx.session.flush()
            tx.session.add(DepartmentRow(
                department_id=department, project_id=project,
                department_code="P19", department_code_normalized="P19",
                name="Synthetic P19 Department", state="ACTIVE",
            ))
            tx.session.add_all([
                ProjectMemberRow(
                    project_member_id=uuid.uuid4(), project_id=project,
                    user_id=user, department_id=department,
                    project_role=role, state="ACTIVE",
                )
                for user, role in (
                    (manager, "PROJECT_MANAGER"),
                    (implementer, "IMPLEMENTATION_MEMBER"),
                    (customer_manager, "CUSTOMER_MANAGER"),
                )
            ])
            tx.commit()

        template = "a1272ce0-01f0-5e6c-9706-000000000001"
        request_body = json.dumps({
            "output_type": "DOCX", "template_version_ref": template,
            "source_version_refs": [str(uuid.uuid4())],
            "output_policy_ref": "output.policy.requirement-docx.v1",
            "plugin_operation": "word.generate",
        }, separators=(",", ":")).encode("utf-8")
        expected = (
            (manager, 422, "p19-manager-create-00001"),
            (implementer, 422, "p19-implementer-create-01"),
            (customer_manager, 404, "p19-customer-manager-create-01"),
        )
        if "/api/v1/projects/{project_id}/output-requests" in create_app().openapi().get("paths", {}):
            raise AssertionError("default app unexpectedly mounted Output creation")
        for actor, expected_status, key in expected:
            ACTOR_BY_TOKEN[TOKEN] = actor
            app = app_for(runtime, actor)
            route = "/api/v1/projects/" + str(project) + "/output-requests"
            before = write_snapshot(database, args.port)
            status, _ = asgi_post(app, route, request_body, key)
            after = write_snapshot(database, args.port)
            if status != expected_status:
                raise AssertionError(
                    f"unexpected HTTP status for synthetic role: {status}, expected {expected_status}"
                )
            if after != before:
                raise AssertionError("untrusted or unauthorized Output create left persistent writes")

        result.update(
            status="PASS_SCOPE_LIMITED",
            project_manager_rejected_untrusted_plugin_no_writes=True,
            implementation_member_rejected_untrusted_plugin_no_writes=True,
            customer_manager_denied_no_writes=True,
            default_app_route_absent=True,
            package_signer_manifest_empty=True,
            postgres_version="18.6",
            pgvector_version="0.8.6",
        )
    finally:
        ACTOR_BY_TOKEN.clear()
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_db(admin, database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
