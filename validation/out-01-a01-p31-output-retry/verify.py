from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import URL, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend/src"))

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobLeaseRow, JobRow
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureError,
)
from plm_assistant.modules.output.application.retry_generation import (
    OUTPUT_RETRY_DELAY_SECONDS, OutputGenerationRetryError,
    OutputGenerationRetryOwner,
)
from plm_assistant.modules.output.application.start_generation import OutputGenerationStartOwner
from plm_assistant.modules.output.infrastructure.fail_generation import (
    SqlAlchemyOutputGenerationFailureRepository,
)
from plm_assistant.modules.output.infrastructure.orm import OutputContextSnapshotRow, OutputRequestRow
from plm_assistant.modules.output.infrastructure.retry_generation_repository import (
    SqlAlchemyOutputGenerationRetryRepository,
)
from plm_assistant.modules.output.infrastructure.start_generation_repository import (
    SqlAlchemyOutputGenerationStartRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def db_url(name, port):
    return URL.create("postgresql+psycopg", username="postgres", host="127.0.0.1",
                      port=port, database=name)


def admin_dsn(port):
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def dsn(name, port):
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def retry_owner(runtime, jobs, system, *, failing_audit=False):
    return OutputGenerationRetryOwner(
        unit_of_work=runtime.unit_of_work, jobs=jobs,
        repository=SqlAlchemyOutputGenerationRetryRepository(),
        audit=(FailingAudit() if failing_audit else AuditService(SqlAlchemyAuditRepository())),
        system_actor_id=system)


def snapshot(database, port, request, job):
    with psycopg.connect(dsn(database, port)) as conn:
        out = conn.execute(
            "SELECT request_state,current_execution_ref,lock_version,completed_at "
            "FROM plm.out_output_requests WHERE output_request_id=%s", (request,)).fetchone()
        job_row = conn.execute(
            "SELECT state,available_at,completed_at,lease_expires_at FROM plm.job_jobs "
            "WHERE job_id=%s", (job,)).fetchone()
        lease = conn.execute("SELECT state FROM plm.job_leases WHERE job_id=%s",
                             (job,)).fetchone()
        attempt = conn.execute(
            "SELECT completed_at,error_code FROM plm.job_attempts WHERE job_id=%s",
            (job,)).fetchone()
        audit = conn.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
            "AND action IN ('OUTPUT_GENERATION_STARTED','OUTPUT_GENERATION_RETRY_SCHEDULED',"
            "'OUTPUT_GENERATION_RETRY_EXHAUSTED')", (request,)).fetchone()[0]
    return out, job_row, lease, attempt, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    temp = Path(os.environ.get("RUNNER_TEMP", ""))
    if (sys.platform != "win32" or not 1 <= args.port <= 65535
            or not re.fullmatch(r"[0-9]{1,12}", args.run_id)
            or temp.drive.casefold() != "d:"):
        raise ValueError("Windows hosted PG and D-drive runner temp required")
    database = "plm_out_p31_" + args.run_id[-10:]
    created, runtime = False, None
    try:
        with psycopg.connect(admin_dsn(args.port), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        created = True
        upgrade_database(db_url(database, args.port), "head")
        runtime = create_database_runtime(db_url(database, args.port))
        requester, system, project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        items = []
        for index in range(3):
            job, request, snapshot_id, source, template, trace = (uuid.uuid4() for _ in range(6))
            refs = {"output_request_id": str(request),
                    "context_snapshot_id": str(snapshot_id)}
            items.append((job, request, snapshot_id, source, template, trace, refs))
        with runtime.unit_of_work() as tx:
            tx.session.add_all([
                UserRow(user_id=requester, username_display="p31-requester",
                        username_normalized="p31-requester", state="DISABLED",
                        deployment_role="NONE"),
                UserRow(user_id=system, username_display="p31-system",
                        username_normalized="p31-system", state="DISABLED",
                        deployment_role="NONE"),
                ProjectRow(project_id=project, project_code="P31-SYNTHETIC",
                           project_code_normalized="P31-SYNTHETIC",
                           name="P31 Synthetic Output", created_by=requester)])
            tx.session.flush()
            for n,(job,request,snapshot_id,source,template,trace,refs) in enumerate(items):
                tx.session.add(OutputContextSnapshotRow(
                    context_snapshot_id=snapshot_id, project_id=project,
                    source_version_refs=[str(source)], context_payload={"synthetic": True},
                    context_fingerprint=b"r"*32, created_by=requester))
                tx.session.add(JobRow(
                    job_id=job, owner_module="output", job_type="OUTPUT_GENERATE",
                    scope="PROJECT", project_id=project, actor_ref=requester,
                    trace_id=str(trace), payload_refs=refs,
                    idempotency_key=f"p31-job-{n}",
                    max_attempts=1 if n == 1 else 3))
            tx.session.flush()
            for n,(job,request,snapshot_id,source,template,trace,refs) in enumerate(items):
                tx.session.add(OutputRequestRow(
                    output_request_id=request, project_id=project, output_type="DOCX",
                    template_version_ref=template, source_version_refs=[str(source)],
                    output_policy_ref="p31.synthetic.v1", plugin_operation="word.generate",
                    context_snapshot_id=snapshot_id, input_fingerprint=bytes([n+31])*32,
                    generation_no=1, request_state="QUEUED", job_ref=job,
                    current_execution_ref=None, idempotency_key=f"p31-request-{n}",
                    trace_id=trace, requested_by=requester, lock_version=0))
            tx.commit()

        jobs = SqlAlchemyJobLeaseRepository()
        queue = JobLeaseService(unit_of_work=runtime.unit_of_work, repository=jobs)
        worker = "p31-output-worker"
        claims = [queue.claim_next_output(worker_ref=worker, lease_seconds=300) for _ in items]
        by_job = {c.job_id: c for c in claims if c is not None}
        if set(by_job) != {x[0] for x in items}:
            raise AssertionError("P31 fixtures were not leased")
        starter = OutputGenerationStartOwner(
            unit_of_work=runtime.unit_of_work, jobs=jobs,
            repository=SqlAlchemyOutputGenerationStartRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()), system_actor_id=system)
        for item in items:
            starter.start(by_job[item[0]], worker_ref=worker)

        retry_item, exhausted_item, rollback_item = items
        owner = retry_owner(runtime, jobs, system)
        retry_result = owner.retry(
            by_job[retry_item[0]], worker_ref=worker,
            error_code="OUTPUT_STORAGE_TEMPORARY")
        retry_state = snapshot(database, args.port, retry_item[1], retry_item[0])
        if (retry_result.job_state != "RETRY_WAIT"
                or retry_result.retry_delay_seconds != OUTPUT_RETRY_DELAY_SECONDS
                or retry_state[0][0] != "QUEUED" or retry_state[0][1] is not None
                or retry_state[0][2] != 2 or retry_state[0][3] is not None
                or retry_state[1][0] != "RETRY_WAIT" or retry_state[1][3] is not None
                or retry_state[2][0] != "RELEASED"
                or retry_state[3][0] is None
                or retry_state[3][1] != "OUTPUT_STORAGE_TEMPORARY"
                or retry_state[4] != 2):
            raise AssertionError("retry did not atomically return Output to QUEUED")

        exhausted_result = owner.retry(
            by_job[exhausted_item[0]], worker_ref=worker,
            error_code="OUTPUT_PLUGIN_BUSY")
        exhausted = snapshot(database, args.port, exhausted_item[1], exhausted_item[0])
        if (exhausted_result.job_state != "FAILED"
                or exhausted_result.retry_delay_seconds != 0
                or exhausted[0][0] != "FAILED" or exhausted[0][2] != 2
                or exhausted[0][3] is None or exhausted[1][0] != "FAILED"
                or exhausted[2][0] != "RELEASED" or exhausted[4] != 2):
            raise AssertionError("attempt exhaustion did not atomically fail Output")

        rollback_claim = by_job[rollback_item[0]]
        before = snapshot(database, args.port, rollback_item[1], rollback_item[0])
        for candidate, who, code in (
            (rollback_claim, "attacker", "OUTPUT_GENERATION_TRANSIENT"),
            (replace_token(rollback_claim), worker, "OUTPUT_GENERATION_TRANSIENT"),
            (rollback_claim, worker, "sensitive details"),
        ):
            try:
                owner.retry(candidate, worker_ref=who, error_code=code)
            except OutputGenerationRetryError:
                pass
            else:
                raise AssertionError("invalid retry input was accepted")
            if snapshot(database, args.port, rollback_item[1], rollback_item[0]) != before:
                raise AssertionError("rejected retry left partial changes")

        try:
            retry_owner(runtime, jobs, system, failing_audit=True).retry(
                rollback_claim, worker_ref=worker,
                error_code="OUTPUT_GENERATION_TRANSIENT")
        except OutputGenerationRetryError:
            pass
        else:
            raise AssertionError("Audit failure did not abort retry")
        if snapshot(database, args.port, rollback_item[1], rollback_item[0]) != before:
            raise AssertionError("Audit failure did not restore both owners")

        with runtime.unit_of_work() as tx:
            events = tx.session.execute(text(
                "SELECT action,outcome,before_state,after_state,actor_type,actor_id,original_actor_id "
                "FROM plm.aud_events WHERE target_object_id=:request "
                "AND action IN ('OUTPUT_GENERATION_RETRY_SCHEDULED',"
                "'OUTPUT_GENERATION_RETRY_EXHAUSTED') "),
                {"request": retry_item[1]}).all()
            event_exhausted = tx.session.execute(text(
                "SELECT action,outcome,before_state,after_state,actor_type,actor_id,original_actor_id "
                "FROM plm.aud_events WHERE target_object_id=:request "
                "AND action='OUTPUT_GENERATION_RETRY_EXHAUSTED'"),
                {"request": exhausted_item[1]}).one()
        if tuple(events[0]) != ("OUTPUT_GENERATION_RETRY_SCHEDULED","SUCCESS",
                               "GENERATING","QUEUED","SYSTEM",system,requester):
            raise AssertionError("retry Audit projection mismatch")
        if tuple(event_exhausted) != ("OUTPUT_GENERATION_RETRY_EXHAUSTED","FAILED",
                                      "GENERATING","FAILED","SYSTEM",system,requester):
            raise AssertionError("exhausted Audit projection mismatch")
        print(json.dumps({
            "status":"PASS_SCOPE_LIMITED","wbs":"OUT-01-A01-P31",
            "transient_failure_requeued_atomically":True,
            "retry_delay_seconds":OUTPUT_RETRY_DELAY_SECONDS,
            "attempt_exhaustion_failed_atomically":True,
            "job_and_output_audit_same_uow":True,
            "wrong_worker_stale_token_and_free_text_denied":True,
            "audit_failure_rolled_back_both_owners":True,
            "plugin_executed":False,"files_generated":False,
            "external_api_calls":0,"customer_data":False,"runner_drive":"D:"
        },sort_keys=True))
        return 0
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            with psycopg.connect(admin_dsn(args.port), autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


def replace_token(claim):
    from dataclasses import replace
    return replace(claim, fencing_token=claim.fencing_token-1)


if __name__ == "__main__":
    raise SystemExit(main())
