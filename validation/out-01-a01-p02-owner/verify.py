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
from plm_assistant.modules.output.application.resolve_context import (
    FixedSourceVersion, PluginOperationCapability, TrustedOutputContextResolver,
)
from plm_assistant.modules.output.infrastructure.builtin_policy_registry import (
    BUILTIN_PLAN_DOCX_POLICY_REF, BuiltinOutputPolicyRegistry,
)
from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
    BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID, BuiltinOutputTemplateRegistry,
)
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import downgrade_database, upgrade_database
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


class SyntheticPlanSource:
    def __init__(self, project_id: uuid.UUID, version_id: uuid.UUID) -> None:
        self.project_id, self.version_id = project_id, version_id
        self.review_state = "APPROVED"
        self.calls = 0

    def read_authorized_fixed_version(self, transaction: object, *, actor_id: uuid.UUID,
                                      project_id: uuid.UUID,
                                      source_version_ref: uuid.UUID) -> FixedSourceVersion | None:
        self.calls += 1
        if project_id != self.project_id or source_version_ref != self.version_id:
            return None
        return FixedSourceVersion(
            project_id=project_id, source_version_ref=source_version_ref,
            source_kind="PLAN_VERSION", review_state=self.review_state,
            authorized=True,
            fields={
                "version_no": 2, "wbs_items": [{"wbs_code": "P42-01",
                                                  "name": "Synthetic task"}],
                "dependencies": [], "milestones": [], "exclusions": [],
                "internal_unapproved_field": "must not persist",
            },
        )


class SyntheticTrustedOperation:
    """Test-only operation capability; never invokes PluginService or a process."""

    def get_operation(self, transaction: object, *, operation_id: str) -> PluginOperationCapability:
        return PluginOperationCapability(
            operation_id=operation_id, output_types=("DOCX",),
            enabled=True, trusted=True,
        )


def verify_plan_source_output_persistence(runtime: object, actor: uuid.UUID,
                                          port: int) -> dict[str, object]:
    project, other_project = uuid.uuid4(), uuid.uuid4()
    version, draft_version = uuid.uuid4(), uuid.uuid4()
    trace, template = uuid.uuid4(), BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID
    with runtime.unit_of_work() as uow:
        uow.session.add(ProjectRow(
            project_id=project, project_code="P42-" + project.hex[:12].upper(),
            project_code_normalized="P42-" + project.hex[:12].upper(),
            name="Synthetic Plan Output", created_by=actor,
        ))
        uow.commit()

    source = SyntheticPlanSource(project, version)
    resolver = TrustedOutputContextResolver(
        sources=source, templates=BuiltinOutputTemplateRegistry(),
        policies=BuiltinOutputPolicyRegistry(),
        operations=SyntheticTrustedOperation(),
    )
    owner = service(runtime, actor, resolver=resolver)

    def plan_command(ref: uuid.UUID, project_ref: uuid.UUID = project) -> CreateOutputRequest:
        return CreateOutputRequest(
            b"synthetic-session", b"synthetic-csrf", trace, project_ref,
            "DOCX", template, (ref,), BUILTIN_PLAN_DOCX_POLICY_REF,
            "word.generate",
        )

    request = plan_command(version)
    first = owner.create(request, idempotency_key="p42-plan-source-key-000001")
    replay = owner.create(request, idempotency_key="p42-plan-source-key-000001")
    if (first.output_request_id, first.job_id) != (replay.output_request_id, replay.job_id):
        raise AssertionError("PlanVersion Output replay changed Request/Job references")

    expected_counts = (1, 1, 1, 1, 1, 1)
    database_dsn = dsn(runtime._engine.url.database, port)
    committed = row_counts(database_dsn, project)
    if committed != expected_counts:
        raise AssertionError(f"unexpected Plan source Output persistence: {committed!r}")
    if row_counts(database_dsn, other_project) != (0, 0, 0, 0, 0, 0):
        raise AssertionError("cross-project Plan source request persisted data")

    with psycopg.connect(database_dsn) as connection:
        row = connection.execute(
            "SELECT r.output_request_id, r.context_snapshot_id, r.source_version_refs, "
            "c.context_payload, j.job_id, j.payload_refs, "
            "(SELECT count(*) FROM plm.job_outbox_events e "
            " WHERE e.project_id=r.project_id AND e.aggregate_ref=r.output_request_id), "
            "(SELECT count(*) FROM plm.plg_executions x WHERE x.project_id=r.project_id) "
            "FROM plm.out_output_requests r "
            "JOIN plm.out_context_snapshots c ON c.context_snapshot_id=r.context_snapshot_id "
            "JOIN plm.job_jobs j ON j.job_id=%s "
            "WHERE r.project_id=%s AND r.output_request_id=%s",
            (first.job_id, project, first.output_request_id),
        ).fetchone()
    if row is None:
        raise AssertionError("Plan source Output rows could not be joined")
    request_id, snapshot_id, source_refs, payload, job_id, job_payload, outbox_count, execution_count = row
    expected_fields = {
        "version_no": 2,
        "wbs_items": [{"wbs_code": "P42-01", "name": "Synthetic task"}],
        "dependencies": [], "milestones": [], "exclusions": [],
    }
    if (request_id != first.output_request_id or job_id != first.job_id
            or source_refs != [str(version)]
            or payload["sources"][0]["source_version_ref"] != str(version)
            or payload["sources"][0]["source_kind"] != "PLAN_VERSION"
            or payload["sources"][0]["review_state"] != "APPROVED"
            or payload["sources"][0]["fields"] != expected_fields
            or "internal_unapproved_field" in payload["sources"][0]["fields"]
            or job_payload.get("payload_refs", {}).get("context_snapshot_id") == str(snapshot_id)
            or job_payload.get("context_snapshot_id") != str(snapshot_id)
            or outbox_count != 1 or execution_count != 0):
        raise AssertionError("PlanVersion context/Job/Outbox persisted unexpected data")

    before = row_counts(database_dsn, project)
    source.review_state = "DRAFT"
    try:
        owner.create(plan_command(draft_version), idempotency_key="p42-draft-key-000001")
    except OutputRequestError:
        pass
    else:
        raise AssertionError("DRAFT PlanVersion was accepted by Plan policy")
    if row_counts(database_dsn, project) != before:
        raise AssertionError("DRAFT PlanVersion failure left writes")

    return {
        "status": "PASS_SCOPE_LIMITED",
        "request_job_snapshot_outbox_atomic": True,
        "same_key_replay": True,
        "approved_plan_source": True,
        "draft_source_rejected_without_writes": True,
        "field_allowlist": True,
        "plugin_execution_count": execution_count,
        "test_operation_capability_only": True,
        "customer_data": False,
    }


class FailingAudit:
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        raise RuntimeError("synthetic audit failure")


def service(runtime: object, actor: uuid.UUID, *, denied: bool = False, audit: object | None = None,
            resolver: object | None = None) -> OutputRequestService:
    return OutputRequestService(
        unit_of_work=runtime.unit_of_work,
        access=SyntheticAccess(actor, denied=denied),
        license_guard=SyntheticLicense(),
        resolver=resolver or SyntheticResolver(),
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


def history_snapshot(database_dsn: str, project_id: uuid.UUID) -> tuple[tuple[tuple[object, ...], ...], ...]:
    queries = (
        ("SELECT context_snapshot_id, project_id, context_fingerprint FROM plm.out_context_snapshots WHERE project_id=%s ORDER BY context_snapshot_id",),
        ("SELECT output_request_id, project_id, job_ref, context_snapshot_id, idempotency_key FROM plm.out_output_requests WHERE project_id=%s ORDER BY output_request_id",),
        ("SELECT job_id, project_id, idempotency_key FROM plm.job_jobs WHERE project_id=%s AND owner_module='output' ORDER BY job_id",),
        ("SELECT event_id, project_id, aggregate_ref, idempotency_key FROM plm.job_outbox_events WHERE project_id=%s AND owner_module='output' ORDER BY event_id",),
        ("SELECT audit_event_id, target_project_id, target_object_id FROM plm.aud_events WHERE target_project_id=%s AND action='OUTPUT_REQUEST_CREATE' ORDER BY audit_event_id",),
        ("SELECT receipt_id, project_id, operation, key_digest, result_ref_id FROM plm.plt_idempotency_receipts WHERE project_id=%s AND operation='V1_OUTPUT_REQUEST_CREATE' ORDER BY receipt_id",),
    )
    with psycopg.connect(database_dsn) as connection:
        return tuple(tuple(row) for (query,) in queries
                     for row in connection.execute(query, (project_id,)).fetchall())


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

        database_dsn = dsn(database, args.port)
        snapshot_id = None
        with psycopg.connect(database_dsn) as connection:
            snapshot_id = connection.execute(
                "SELECT context_snapshot_id FROM plm.out_context_snapshots "
                "WHERE project_id=%s ORDER BY context_snapshot_id LIMIT 1",
                (project,),
            ).fetchone()[0]
        for statement in (
            "UPDATE plm.out_context_snapshots SET context_payload='{}'::jsonb WHERE context_snapshot_id=%s",
            "DELETE FROM plm.out_context_snapshots WHERE context_snapshot_id=%s",
        ):
            with psycopg.connect(database_dsn, autocommit=True) as connection:
                try:
                    connection.execute(statement, (snapshot_id,))
                except psycopg.Error:
                    pass
                else:
                    raise AssertionError("immutable ContextSnapshot mutation was accepted")
        if row_counts(database_dsn, project) != committed:
            raise AssertionError("rejected ContextSnapshot mutation changed stored rows")

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

        plan_output_validation = verify_plan_source_output_persistence(runtime, actor, args.port)
        history_before = history_snapshot(database_dsn, project)
        runtime.dispose()
        runtime = None
        downgrade_database(database_url, "20261102_0220")
        if history_snapshot(database_dsn, project) != history_before:
            raise AssertionError("0221 downgrade changed existing Output history")
        upgrade_database(database_url, "head")
        if history_snapshot(database_dsn, project) != history_before:
            raise AssertionError("0221 re-upgrade changed existing Output history")
        result.update(status="PASS_LIMITED", postgresql="18.x hosted temporary database",
                      project_rows=2, request_job_outbox_audit_rows=2,
                      idempotency_receipt_rows=4, concurrent_generation_coalesced=True,
                      same_key_replay=True, different_payload_conflict=True,
                      audit_failure_rolled_back=True, denied_call_wrote_nothing=True,
                      raw_idempotency_key_persisted=False,
                      context_immutable_update_delete=True,
                      migration_history_preserved_across_downgrade=True,
                      plan_version_output_persistence=plan_output_validation)
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_db(admin_dsn, database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
