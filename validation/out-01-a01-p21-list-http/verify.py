"""Hosted PostgreSQL 18 HTTP checks for OutputRequest list composition."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

import psycopg
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_output_list import (
    create_windows_output_request_list_router,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobQueue
from plm_assistant.modules.jobs.infrastructure.output_enqueue_repository import SqlAlchemyOutputJobQueueRepository
from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec
from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest, OutputRequestService, ResolvedOutputContext,
)
from plm_assistant.modules.output.infrastructure.create_request_repository import SqlAlchemyOutputRequestRepository
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow, ProjectMemberRow, ProjectRow

TOKEN = b"r" * 32
CSRF = b"s" * 32


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
    def validate(self, token, **_kwargs):
        if token != TOKEN:
            raise RuntimeError("synthetic session rejected")
        return True


class SyntheticReadAccess:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, transaction, *, session_token, now):
        if session_token != TOKEN:
            return None
        return self.actor


class SyntheticOrigins:
    def require_trusted_host(self, headers):
        if not any(name.lower() == b"host" and value == b"localhost"
                   for name, value in headers):
            raise RuntimeError("synthetic host rejected")


class SyntheticLicense:
    def require_valid(self, **_kwargs):
        return True


class CreateAccess:
    def __init__(self, actor):
        self.actor = actor

    def authorized_creator(self, *_args, **_kwargs):
        return self.actor


class SyntheticResolver:
    def resolve(self, transaction, *, actor_id, command):
        del transaction, actor_id
        payload = {"source_refs": [str(v) for v in command.source_version_refs]}
        return ResolvedOutputContext(
            command.source_version_refs, payload,
            canonical_payload_fingerprint(payload),
        )


def create_request(runtime, actor, project, ordinal):
    source, template, trace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    command = CreateOutputRequest(
        b"x" * 32, b"y" * 32, trace, project, "DOCX", template, (source,),
        "output.policy.synthetic.v1", "word.generate",
    )
    service = OutputRequestService(
        unit_of_work=runtime.unit_of_work,
        access=CreateAccess(actor),
        license_guard=SyntheticLicense(),
        resolver=SyntheticResolver(),
        repository=SqlAlchemyOutputRequestRepository(),
        jobs=OutputJobQueue(SqlAlchemyOutputJobQueueRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(),
        audit=AuditService(SqlAlchemyAuditRepository()),
    )
    return service.create(
        command, idempotency_key=f"p21-list-fixture-{ordinal:05d}")


async def asgi_get(app, path: str):
    messages = []
    consumed = False

    async def receive():
        nonlocal consumed
        if not consumed:
            consumed = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(
        {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
         "http_version": "1.1", "method": "GET", "scheme": "http",
         "path": path, "raw_path": path.split("?", 1)[0].encode("ascii"),
         "query_string": path.split("?", 1)[1].encode("ascii") if "?" in path else b"",
         "headers": ((b"host", b"localhost"),
                     (b"cookie", b"plm_session=" + TOKEN.hex().encode("ascii"))),
         "client": ("127.0.0.1", 43000), "server": ("localhost", 80)},
        receive, send,
    )
    start = next(item for item in messages if item["type"] == "http.response.start")
    payload = b"".join(item.get("body", b"") for item in messages
                       if item["type"] == "http.response.body")
    return start["status"], payload


def row_counts(database: str, port: int) -> dict[str, int]:
    with psycopg.connect(dsn(database, port)) as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='plm' AND (table_name LIKE 'out%' "
            "OR table_name LIKE 'job%' OR table_name LIKE 'aud%' "
            "OR table_name LIKE 'plt_idempotency%') ORDER BY table_name"
        ).fetchall()
        return {name: conn.execute(f'SELECT count(*) FROM plm."{name}"').fetchone()[0]
                for (name,) in rows}


def read_app(runtime, actor):
    router = create_windows_output_request_list_router(
        runtime=runtime, sessions=SyntheticSessions(),
        origins=SyntheticOrigins(), license_guard=SyntheticLicense(),
        cursors=OutputRequestListCursorCodec(b"o" * 32),
        session_access=SyntheticReadAccess(actor),
    )
    return create_app(output_request_list_router=router)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("temporary loopback PG and numeric hosted run ID required")

    database = "plm_out21_" + args.run_id[-10:]
    admin = dsn("postgres", args.port)
    created = False
    runtime = None
    result = {
        "status": "PENDING", "customer_data": False,
        "external_api_calls": 0, "database": "isolated synthetic PostgreSQL 18.6",
        "product_api_started": False,
    }
    try:
        create_db(admin, database)
        created = True
        upgrade_database(url(database, args.port), "head")
        runtime = create_database_runtime(url(database, args.port))
        creator, manager, implementer, customer_manager, customer_member, outsider, project, other_project = (
            uuid.uuid4() for _ in range(8)
        )
        department, other_department = uuid.uuid4(), uuid.uuid4()
        names = (
            (creator, "p21-creator"), (manager, "p21-manager"),
            (implementer, "p21-implementer"),
            (customer_manager, "p21-customer-manager"),
            (customer_member, "p21-customer-member"), (outsider, "p21-outsider"),
        )
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=user, username_display=name,
                        username_normalized=name, state="DISABLED",
                        deployment_role="NONE")
                for user, name in names
            ])
            tx.session.flush()
            tx.session.add_all([
                ProjectRow(project_id=project, project_code="P21-A",
                    project_code_normalized="P21-A",
                    name="Synthetic P21 Output List", created_by=creator),
                ProjectRow(project_id=other_project, project_code="P21-B",
                    project_code_normalized="P21-B",
                    name="Synthetic P21 Other Project", created_by=creator),
            ])
            tx.session.flush()
            tx.session.add_all([
                DepartmentRow(department_id=department, project_id=project,
                    department_code="P21", department_code_normalized="P21",
                    name="Synthetic P21 Department", state="ACTIVE"),
                DepartmentRow(department_id=other_department, project_id=other_project,
                    department_code="P21B", department_code_normalized="P21B",
                    name="Synthetic P21 Other Department", state="ACTIVE"),
            ])
            tx.session.flush()
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
                    (customer_member, "CUSTOMER_MEMBER"),
                )
            ])
            tx.commit()

        for ordinal in range(3):
            create_request(runtime, creator, project, ordinal)
        app = read_app(runtime, manager)
        before = row_counts(database, args.port)
        status, body = asyncio.run(asgi_get(
            app, f"/api/v1/projects/{project}/output-requests?page_size=1"))
        if status != 200:
            raise AssertionError(f"authorized list page returned HTTP {status}: {body!r}")
        first = json.loads(body)["data"]
        if len(first["items"]) != 1 or not first["has_more"] or not first["next_cursor"]:
            raise AssertionError("first Output list page is incomplete")
        next_path = f"/api/v1/projects/{project}/output-requests?page_size=1&cursor={first['next_cursor']}"
        next_status, next_body = asyncio.run(asgi_get(app, next_path))
        second = json.loads(next_body)["data"] if next_status == 200 else {}
        if (next_status != 200 or len(second.get("items", [])) != 1
                or second["items"][0]["output_request_id"] == first["items"][0]["output_request_id"]):
            raise AssertionError("cursor pagination did not return the next distinct item")
        replay_status, _ = asyncio.run(asgi_get(
            app, f"/api/v1/projects/{other_project}/output-requests?page_size=1&cursor={first['next_cursor']}"))
        tampered = first["next_cursor"][:-1] + ("A" if first["next_cursor"][-1] != "A" else "B")
        tamper_status, _ = asyncio.run(asgi_get(
            app, f"/api/v1/projects/{project}/output-requests?page_size=1&cursor={tampered}"))
        member_status, _ = asyncio.run(asgi_get(
            read_app(runtime, implementer),
            f"/api/v1/projects/{project}/output-requests?page_size=2"))
        manager_status, _ = asyncio.run(asgi_get(
            read_app(runtime, customer_manager),
            f"/api/v1/projects/{project}/output-requests?page_size=2"))
        customer_status, _ = asyncio.run(asgi_get(
            read_app(runtime, customer_member),
            f"/api/v1/projects/{project}/output-requests?page_size=2"))
        outsider_status, _ = asyncio.run(asgi_get(
            read_app(runtime, outsider),
            f"/api/v1/projects/{project}/output-requests?page_size=2"))
        after = row_counts(database, args.port)
        if (replay_status != 400 or tamper_status != 400
                or member_status != 200 or manager_status != 200
                or customer_status != 404 or outsider_status != 404):
            raise AssertionError("cursor binding or frozen role/project authorization failed")
        if before != after:
            raise AssertionError("Output list GET changed persistent rows")
        default_path = f"/api/v1/projects/{project}/output-requests"
        if default_path in create_app().openapi().get("paths", {}):
            raise AssertionError("default app unexpectedly mounted Output list GET")
        result.update(
            status="PASS_SCOPE_LIMITED",
            project_manager_allowed=True, implementation_member_allowed=True,
            customer_manager_allowed=True, customer_member_denied_404=True,
            nonmember_and_cross_project_denied_404=True,
            cursor_page_size_and_project_binding_checked=True,
            cursor_tampering_denied=True, read_only_row_counts_unchanged=True,
            default_app_route_absent=True, postgres_version="18.6",
            pgvector_version="0.8.6",
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_db(admin, database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
