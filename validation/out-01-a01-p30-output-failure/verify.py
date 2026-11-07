from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import URL, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend/src"))

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, JobLeaseService,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow, JobLeaseRow, JobRow
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureError, OutputGenerationFailureOwner,
)
from plm_assistant.modules.output.application.start_generation import (
    OutputGenerationStartOwner,
)
from plm_assistant.modules.output.infrastructure.fail_generation_repository import (
    SqlAlchemyOutputGenerationFailureRepository,
)
from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextSnapshotRow, OutputRequestRow,
)
from plm_assistant.modules.output.infrastructure.start_generation_repository import (
    SqlAlchemyOutputGenerationStartRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


def db_url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres", host="127.0.0.1",
                      port=port, database=name)


def admin_dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def database_dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def owner(runtime, jobs, system_actor, *, failing_audit=False):
    return OutputGenerationFailureOwner(
        unit_of_work=runtime.unit_of_work,
        jobs=jobs,
        repository=SqlAlchemyOutputGenerationFailureRepository(),
        audit=(FailingAudit() if failing_audit
               else AuditService(SqlAlchemyAuditRepository())),
        system_actor_id=system_actor,
    )


def snapshot(database: str, port: int, request: uuid.UUID,
             job: uuid.UUID) -> tuple[object, ...]:
    with psycopg.connect(database_dsn(database, port)) as conn:
        out = conn.execute(
            "SELECT request_state, current_execution_ref, lock_version, completed_at "
            "FROM plm.out_output_requests WHERE output_request_id=%s", (request,)
        ).fetchone()
        job_state = conn.execute(
            "SELECT state, completed_at, lease_expires_at FROM plm.job_jobs WHERE job_id=%s",
            (job,),
        ).fetchone()
        lease = conn.execute(
            "SELECT state FROM plm.job_leases WHERE job_id=%s", (job,)
        ).fetchone()
        attempt = conn.execute(
            "SELECT completed_at, error_code FROM plm.job_attempts WHERE job_id=%s",
            (job,),
        ).fetchone()
        audit = conn.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
            "AND action IN ('OUTPUT_GENERATION_STARTED','OUTPUT_GENERATION_FAILED')",
            (request,),
        ).fetchone()[0]
    return out, job_state, lease, attempt, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    runner_temp = Path(os.environ.get("RUNNER_TEMP", ""))
    if (sys.platform != "win32" or not 1 <= args.port <= 65535
            or not re.fullmatch(r"[0-9]{1,12}", args.run_id)
            or runner_temp.drive.casefold() != "d:"):
        raise ValueError("Windows hosted PostgreSQL and D-drive runner temp required")

    database = "plm_out_p30_" + args.run_id[-10:]
    created, runtime = False, None
    try:
        with psycopg.connect(admin_dsn(args.port), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        created = True
        upgrade_database(db_url(database, args.port), "head")
        runtime = create_database_runtime(db_url(database, args.port))
        requester, system_actor, project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        items = []
        for n in range(2):
            job_id, request_id, snapshot_id, source_id, template_id, trace = (
                uuid.uuid4() for _ in range(6))
            refs = {"output_request_id": str(request_id),
                    "context_snapshot_id": str(snapshot_id)}
            items.append((job_id, request_id, snapshot_id, source_id, template_id, trace, refs))
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=requester, username_display="p30-requester",
                        username_normalized="p30-requester", state="DISABLED",
                        deployment_role="NONE"),
                UserRow(user_id=system_actor, username_display="p30-system",
                        username_normalized="p30-system", state="DISABLED",
                        deployment_role="NONE"),
                ProjectRow(project_id=project, project_code="P30-SYNTHETIC",
                           project_code_normalized="P30-SYNTHETIC",
                           name="P30 Synthetic Output", created_by=requester),
            ])
            tx.session.flush()
            for n, (job_id, request_id, snapshot_id, source_id, template_id, trace, refs) in enumerate(items):
                tx.session.add(OutputContextSnapshotRow(
                    context_snapshot_id=snapshot_id, project_id=project,
                    source_version_refs=[str(source_id)], context_payload={"synthetic": True},
                    context_fingerprint=b"p" * 32, created_by=requester))
                tx.session.add(JobRow(
                    job_id=job_id, owner_module="output", job_type="OUTPUT_GENERATE",
                    scope="PROJECT", project_id=project, actor_ref=requester,
                    trace_id=str(trace), payload_refs=refs, idempotency_key=f"p30-job-{n}",
                    max_attempts=3))
            tx.session.flush()
            for n, (job_id, request_id, snapshot_id, source_id, template_id, trace, refs) in enumerate(items):
                tx.session.add(OutputRequestRow(
                    output_request_id=request_id, project_id=project, output_type="DOCX",
                    template_version_ref=template_id, source_version_refs=[str(source_id)],
                    output_policy_ref="p30.synthetic.v1", plugin_operation="word.generate",
                    context_snapshot_id=snapshot_id, input_fingerprint=bytes([n + 11]) * 32,
                    generation_no=1, request_state="QUEUED", job_ref=job_id,
                    current_execution_ref=None, idempotency_key=f"p30-request-{n}",
                    trace_id=trace, requested_by=requester, lock_version=0))
            tx.commit()

        lease_repo = SqlAlchemyJobLeaseRepository()
        queue = JobLeaseService(unit_of_work=runtime.unit_of_work, repository=lease_repo)
        worker = "p30-output-worker"
        claims = [queue.claim_next_output(worker_ref=worker, lease_seconds=300)
                  for _ in items]
        by_job = {claim.job_id: claim for claim in claims if claim is not None}
        if set(by_job) != {item[0] for item in items}:
            raise AssertionError("P30 synthetic Output jobs were not leased")
        system = OutputGenerationStartOwner(
            unit_of_work=runtime.unit_of_work, jobs=lease_repo,
            repository=SqlAlchemyOutputGenerationStartRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()), system_actor_id=system_actor)
        for item in items:
            system.start(by_job[item[0]], worker_ref=worker)

        good, audit_case = items
        good_claim = by_job[good[0]]
        before = snapshot(database, args.port, good[1], good[0])
        try:
            owner(runtime, lease_repo, system_actor).fail(
                good_claim, worker_ref="p30-other-worker",
                error_code="OUTPUT_GENERATION_FAILED")
        except OutputGenerationFailureError:
            pass
        else:
            raise AssertionError("wrong worker was accepted")
        if snapshot(database, args.port, good[1], good[0]) != before:
            raise AssertionError("wrong worker left a partial transition")
        try:
            owner(runtime, lease_repo, system_actor).fail(
                good_claim, worker_ref=worker, error_code="private stack trace")
        except OutputGenerationFailureError:
            pass
        else:
            raise AssertionError("unlisted error detail was accepted")
        stale = replace(good_claim, fencing_token=good_claim.fencing_token - 1)
        try:
            owner(runtime, lease_repo, system_actor).fail(
                stale, worker_ref=worker, error_code="OUTPUT_GENERATION_FAILED")
        except OutputGenerationFailureError:
            pass
        else:
            raise AssertionError("stale fencing token was accepted")
        if snapshot(database, args.port, good[1], good[0]) != before:
            raise AssertionError("rejected failures changed Output/Job/Audit")

        result = owner(runtime, lease_repo, system_actor).fail(
            good_claim, worker_ref=worker, error_code="OUTPUT_PLUGIN_UNAVAILABLE")
        after = snapshot(database, args.port, good[1], good[0])
        if (result.state != "FAILED" or result.lock_version != 2 or not result.changed
                or after[0][0] != "FAILED" or after[0][2] != 2 or after[0][3] is None
                or after[1][0] != "FAILED" or after[1][1] is None
                or after[1][2] is not None or after[2][0] != "RELEASED"
                or after[3][0] is None or after[3][1] != "OUTPUT_PLUGIN_UNAVAILABLE"
                or after[4] != 2):
            raise AssertionError("Output/Job failure facts did not commit together")

        second = audit_case
        second_claim = by_job[second[0]]
        before_rollback = snapshot(database, args.port, second[1], second[0])
        try:
            owner(runtime, lease_repo, system_actor, failing_audit=True).fail(
                second_claim, worker_ref=worker,
                error_code="OUTPUT_GENERATION_FAILED")
        except OutputGenerationFailureError:
            pass
        else:
            raise AssertionError("Audit failure did not abort terminal transition")
        if snapshot(database, args.port, second[1], second[0]) != before_rollback:
            raise AssertionError("Audit failure did not roll back Output and Job")

        with runtime.unit_of_work() as tx:
            event = tx.session.execute(text(
                "SELECT actor_type, actor_id, original_actor_id, action, outcome, "
                "before_state, after_state FROM plm.aud_events "
                "WHERE target_object_id=:request AND action='OUTPUT_GENERATION_FAILED'"),
                {"request": good[1]}).one()
        if tuple(event) != ("SYSTEM", system_actor, requester,
                            "OUTPUT_GENERATION_FAILED", "FAILED",
                            "GENERATING", "FAILED"):
            raise AssertionError("system failure audit attribution was incorrect")

        print(json.dumps({
            "status": "PASS_SCOPE_LIMITED", "wbs": "OUT-01-A01-P30",
            "valid_failure_terminalized": True, "job_and_output_failed_atomically": True,
            "worker_error_details_not_persisted": True, "wrong_worker_denied": True,
            "stale_token_denied": True, "audit_failure_rolled_back_both_owners": True,
            "system_actor_and_original_requester_attribution": True,
            "files_generated": False, "plugin_executed": False,
            "external_api_calls": 0, "customer_data": False, "runner_drive": "D:",
        }, sort_keys=True))
        return 0
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            with psycopg.connect(admin_dsn(args.port), autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    raise SystemExit(main())
