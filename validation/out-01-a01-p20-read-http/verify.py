"""Hosted PostgreSQL 18 HTTP checks for OutputRequest detail composition."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
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
from plm_assistant.entrypoints.windows_output_read import (
    create_windows_output_request_read_router,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobQueue
from plm_assistant.modules.jobs.infrastructure.output_enqueue_repository import SqlAlchemyOutputJobQueueRepository
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
_PRIVATE_MARKER = "P20_CONTEXT_MUST_NEVER_LEAVE_DATABASE"


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


class CreateAccess:
    def __init__(self, actor):
        self.actor = actor

    def authorized_creator(self, *_args, **_kwargs):
        return self.actor


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


class SyntheticResolver:
    def resolve(self, transaction, *, actor_id, command):
        del transaction, actor_id
        payload = {
            "source_refs": [str(value) for value in command.source_version_refs],
            "internal_marker": _PRIVATE_MARKER,
            "path": "C:/must-not-be-returned/customer.docx",
        }
        return ResolvedOutputContext(
            command.source_version_refs, payload,
            canonical_payload_fingerprint(payload),
        )


def create_request(runtime, actor, project):
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
    return service.create(command, idempotency_key="p20-read-fixture-00001")


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
         "path": path, "raw_path": path.encode("ascii"), "query_string": b"",
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
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='plm' AND (table_name LIKE 'out%' "
            "OR table_name LIKE 'job%' OR table_name LIKE 'aud%' "
            "OR table_name LIKE 'plt_idempotency%') ORDER BY table_name"
        ).fetchall()
        return {name: conn.execute(f'SELECT count(*) FROM plm."{name}"').fetchone()[0]
                for (name,) in tables}


def read_app(runtime, actor):
    router = create_windows_output_request_read_router(
        runtime=runtime, sessions=SyntheticSessions(),
        origins=SyntheticOrigins(), license_guard=SyntheticLicense(),
        session_access=SyntheticReadAccess(actor),
    )
    return create_app(output_request_read_router=router)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("temporary loopback PG and numeric hosted run ID required")

    database = "plm_out20_" + args.run_id[-10:]
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
        creator, manager, outsider, project, unrelated_project = (
            uuid.uuid4() for _ in range(5)
        )
        department, unrelated_department = uuid.uuid4(), uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=user, username_display=name,
                        username_normalized=name, state="DISABLED",
                        deployment_role="NONE")
                for user, name in (
                    (creator, "p20-synthetic-creator"),
                    (manager, "p20-synthetic-manager"),
                    (outsider, "p20-synthetic-outsider"),
                )
            ])
            tx.session.flush()
            tx.session.add_all([
                ProjectRow(project_id=project, project_code="P20-A",
                    project_code_normalized="P20-A",
                    name="Synthetic P20 Read Project", created_by=creator),
                ProjectRow(project_id=unrelated_project, project_code="P20-B",
                    project_code_normalized="P20-B",
                    name="Synthetic P20 Unrelated Project", created_by=creator),
            ])
            tx.session.flush()
            tx.session.add_all([
                DepartmentRow(department_id=department, project_id=project,
                    department_code="P20", department_code_normalized="P20",
                    name="Synthetic P20 Department", state="ACTIVE"),
                DepartmentRow(department_id=unrelated_department,
                    project_id=unrelated_project, department_code="P20B",
                    department_code_normalized="P20B",
                    name="Synthetic P20 Unrelated Department", state="ACTIVE"),
            ])
            tx.session.flush()
            tx.session.add(ProjectMemberRow(
                project_member_id=uuid.uuid4(), project_id=project,
                user_id=manager, department_id=department,
                project_role="PROJECT_MANAGER", state="ACTIVE",
            ))
            tx.commit()

        request = create_request(runtime, creator, project)
        path = f"/api/v1/projects/{project}/output-requests/{request.output_request_id}"
        app = read_app(runtime, manager)
        before = row_counts(database, args.port)
        status, body = asyncio.run(asgi_get(app, path))
        after = row_counts(database, args.port)
        if status != 200:
            raise AssertionError(f"authorized Output detail GET returned HTTP {status}")
        result_body = json.loads(body)
        data = result_body.get("data")
        if (type(data) is not dict
                or data.get("output_request_id") != str(request.output_request_id)
                or data.get("project_id") != str(project)
                or data.get("state") != "QUEUED"
                or "context_fingerprint" not in data
                or _PRIVATE_MARKER.encode() in body
                or b"must-not-be-returned" in body
                or "context_payload" in data):
            raise AssertionError("Output detail response is incomplete or disclosed context")
        if before != after:
            raise AssertionError("Output detail GET changed persistent rows")

        outsider_app = read_app(runtime, outsider)
        outsider_status, _ = asyncio.run(asgi_get(outsider_app, path))
        cross_status, _ = asyncio.run(asgi_get(
            app, f"/api/v1/projects/{unrelated_project}/output-requests/{request.output_request_id}",
        ))
        if outsider_status != 404 or cross_status != 404:
            raise AssertionError("unauthorized or cross-project Output detail was not 404")
        if "/api/v1/projects/{project_id}/output-requests/{output_request_id}" in create_app().openapi().get("paths", {}):
            raise AssertionError("default app unexpectedly mounted Output detail GET")

        result.update(
            status="PASS_SCOPE_LIMITED",
            authorized_member_get_allowed=True,
            nonmember_get_denied_404=True,
            cross_project_get_denied_404=True,
            context_payload_and_path_not_disclosed=True,
            read_only_row_counts_unchanged=True,
            default_app_route_absent=True,
            postgres_version="18.6",
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
