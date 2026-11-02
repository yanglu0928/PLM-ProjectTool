"""Synthetic PostgreSQL integration for OUT-01-A01-P02 transactional ownership."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import URL, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobQueue
from plm_assistant.modules.jobs.infrastructure.output_enqueue_repository import SqlAlchemyOutputJobQueueRepository
from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest, OutputRequestError, OutputRequestService, ResolvedOutputContext,
)
from plm_assistant.modules.output.infrastructure.create_request_repository import SqlAlchemyOutputRequestRepository
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


def url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres", host="127.0.0.1",
                      port=port, database=name)


def dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def create_db(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(sql.Identifier(name)))


def drop_db(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


class SyntheticAccess:
    def __init__(self, actor_id: uuid.UUID, *, denied: bool = False) -> None:
        self.actor_id, self.denied = actor_id, denied

    def authorized_creator(self, *args: object, **kwargs: object) -> uuid.UUID | None:
        return None if self.denied else self.actor_id


class SyntheticLicense:
    def require_valid(self, *, trace_id: uuid.UUID) -> bool:
        return True


class SyntheticResolver:
    def resolve(self, transaction: object, *, actor_id: uuid.UUID,
                command: CreateOutputRequest) -> ResolvedOutputContext:
        payload = {"source_order": [str(value) for value in command.source_version_refs],
                   "synthetic_fixture": True}
        return ResolvedOutputContext(command.source_version_refs, payload,
                                     canonical_payload_fingerprint(payload))


class FailingAudit:
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        raise RuntimeError("synthetic audit failure")


def service(runtime: object, actor: uuid.UUID, *, denied: bool = False, audit: object | None = None) -> OutputRequestService:
    return OutputRequestService(
        unit_of_work=runtime.unit_of_work,
        access=SyntheticAccess(actor, denied=denied),
        license_guard=SyntheticLicense(),
        resolver=SyntheticResolver(),
        repository=SqlAlchemyOutputRequestRepository(),
        jobs=OutputJobQueue(SqlAlchemyOutputJobQueueRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(),
        audit=audit or AuditService(SqlAlchemyAuditRepository()),
    )


def command(project: uuid.UUID, source: uuid.UUID, template: uuid.UUID, trace: uuid.UUID,
            policy: str = "standard-output.v1") -> CreateOutputRequest:
    return CreateOutputRequest(b"synthetic-session", b"synthetic-csrf", trace, project, "DOCX",
                               template, (source,), policy, "word.generate")


def row_counts(database_dsn: str, project_id: uuid.UUID) -> tuple[int, ...]:
    queries = (
        "SELECT count(*) FROM plm.out_context_snapshots WHERE project_id=%s",
        "SELECT count(*) FROM plm.out_output_requests WHERE project_id=%s",
        "SELECT count(*) FROM plm.job_jobs WHERE project_id=%s AND owner_module='output'",
        "SELECT count(*) FROM plm.job_outbox_events WHERE project_id=%s AND owner_module='output'",
        "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s AND action='OUTPUT_REQUEST_CREATE'",
        "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s AND operation='V1_OUTPUT_REQUEST_CREATE'",
    )
    with psycopg.connect(database_dsn) as connection:
        return tuple(connection.execute(query, (project_id,)).fetchone()[0] for query in queries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("temporary loopback PostgreSQL and numeric workflow run ID required")

    database = "plm_out02_" + args.run_id[-10:]
    admin_dsn = dsn("postgres", args.port)
    created = False
    runtime = None
    result = {"status": "PENDING", "customer_data": False, "external_api_calls": 0,
              "database": "temporary synthetic PostgreSQL only"}
    try:
        create_db(admin_dsn, database)
        created = True
        database_url = url(database, args.port)
        upgrade_database(database_url, "head")
        runtime = create_database_runtime(database_url)
        actor, project, template, source, trace = (uuid.uuid4() for _ in range(5))
        with runtime.unit_of_work() as uow:
            uow.session.add(UserRow(user_id=actor, username_display="synthetic-owner",
                                    username_normalized="synthetic-owner",
                                    state="DISABLED", deployment_role="NONE"))
            uow.session.add(ProjectRow(project_id=project, project_code="P02-SYNTHETIC",
                                       project_code_normalized="P02-SYNTHETIC",
                                       name="Synthetic Output Owner", created_by=actor))
            uow.commit()

        owner = service(runtime, actor)
        request = command(project, source, template, trace)
        first = owner.create(request, idempotency_key="p02-same-key-000001")
        replay = owner.create(request, idempotency_key="p02-same-key-000001")
        coalesced = owner.create(request, idempotency_key="p02-other-key-000001")
        refs = lambda value: (value.output_request_id, value.job_id)
        if refs(first) != refs(replay) or refs(first) != refs(coalesced):
            raise AssertionError("replay or same-generation coalescing changed Request/Job references")

        try:
            owner.create(command(project, uuid.uuid4(), template, uuid.uuid4()),
                         idempotency_key="p02-same-key-000001")
        except OutputRequestError as exc:
            if exc.code != "CONFLICT_IDEMPOTENCY":
                raise
        else:
            raise AssertionError("same key with a different payload did not conflict")

        concurrent_command = command(project, uuid.uuid4(), template, uuid.uuid4())
        def issue(key: str):
            return owner.create(concurrent_command, idempotency_key=key)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pair = list(pool.map(issue, ("p02-race-key-000001", "p02-race-key-000002")))
        if refs(pair[0]) != refs(pair[1]):
            raise AssertionError("concurrent same-generation calls did not converge")

        committed = row_counts(dsn(database, args.port), project)
        if committed != (2, 2, 2, 2, 2, 4):
            raise AssertionError(f"unexpected atomic owner rows: {committed!r}")

        try:
            service(runtime, actor, audit=FailingAudit()).create(
                command(project, uuid.uuid4(), template, uuid.uuid4(), "audit-failure.v1"),
                idempotency_key="p02-audit-failure-0001",
            )
        except OutputRequestError as exc:
            if exc.code != "SYSTEM_UNAVAILABLE":
                raise
        else:
            raise AssertionError("audit failure did not abort OutputRequest creation")
        if row_counts(dsn(database, args.port), project) != committed:
            raise AssertionError("audit failure left partial Output/Job/Outbox/Audit/receipt data")

        try:
            service(runtime, actor, denied=True).create(
                command(project, uuid.uuid4(), template, uuid.uuid4()),
                idempotency_key="p02-denied-key-000001",
            )
        except OutputRequestError as exc:
            if exc.code != "FORBIDDEN":
                raise
        else:
            raise AssertionError("unauthorized request did not fail closed")
        if row_counts(dsn(database, args.port), project) != committed:
            raise AssertionError("unauthorized request left database writes")

        with runtime.unit_of_work() as uow:
            stored = uow.session.execute(text(
                "SELECT idempotency_key FROM plm.out_output_requests "
                "WHERE project_id=:project ORDER BY requested_at LIMIT 1"
            ), {"project": project}).scalar_one()
        if stored != hashlib.sha256(b"p02-same-key-000001").hexdigest():
            raise AssertionError("raw or non-deterministic idempotency key persisted")

        result.update(status="PASS_LIMITED", postgresql="18.x hosted temporary database",
                      project_rows=2, request_job_outbox_audit_rows=2,
                      idempotency_receipt_rows=4, concurrent_generation_coalesced=True,
                      same_key_replay=True, different_payload_conflict=True,
                      audit_failure_rolled_back=True, denied_call_wrote_nothing=True,
                      raw_idempotency_key_persisted=False)
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_db(admin_dsn, database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
