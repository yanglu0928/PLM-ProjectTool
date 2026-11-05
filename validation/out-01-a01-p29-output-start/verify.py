"""Hosted PostgreSQL proof for the P29 atomic Output generation-start transition."""
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
from sqlalchemy import URL, select, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, JobLeaseService,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.output.application.start_generation import (
    OutputGenerationStartError, OutputGenerationStartOwner,
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


def create_db(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(
            sql.Identifier(name)))


def drop_db(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(name)))


class FailingAudit:
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        raise RuntimeError("synthetic audit failure")


def snapshot(database: str, project_id: uuid.UUID, request_id: uuid.UUID,
             job_id: uuid.UUID) -> tuple[tuple[object, ...], ...]:
    with psycopg.connect(database) as connection:
        request = connection.execute(
            "SELECT request_state, current_execution_ref, lock_version "
            "FROM plm.out_output_requests WHERE output_request_id=%s", (request_id,)
        ).fetchone()
        job = connection.execute(
            "SELECT state, fencing_token, attempt_count FROM plm.job_jobs WHERE job_id=%s",
            (job_id,),
        ).fetchone()
        audit_count = connection.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND action='OUTPUT_GENERATION_STARTED'", (project_id,),
        ).fetchone()[0]
    return request, job, audit_count


def make_owner(runtime, system_actor: uuid.UUID, *, failing_audit: bool = False):
    return OutputGenerationStartOwner(
        unit_of_work=runtime.unit_of_work,
        jobs=SqlAlchemyJobLeaseRepository(),
        repository=SqlAlchemyOutputGenerationStartRepository(),
        audit=(FailingAudit() if failing_audit else AuditService(SqlAlchemyAuditRepository())),
        system_actor_id=system_actor,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    runner_temp = os.environ.get("RUNNER_TEMP", "")
    if (sys.platform != "win32" or not 1 <= args.port <= 65535
            or not re.fullmatch(r"[0-9]{1,12}", args.run_id)
            or Path(runner_temp).drive.casefold() != "d:"):
        raise ValueError("Windows hosted PostgreSQL and D-drive runner temp required")

    database = "plm_out_p29_" + args.run_id[-10:]
    created, runtime = False, None
    try:
        create_db(args.port, database)
        created = True
        upgrade_database(db_url(database, args.port), "head")
        runtime = create_database_runtime(db_url(database, args.port))
        actor, system_actor, project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        fixture = []
        for index in range(2):
            job_id, request_id, snapshot_id, source_id, template_id = (
                uuid.uuid4() for _ in range(5))
            trace_id = uuid.uuid4()
            payload = {"output_request_id": str(request_id),
                       "context_snapshot_id": str(snapshot_id)}
            fixture.append((job_id, request_id, snapshot_id, source_id,
                            template_id, trace_id, payload))
        with runtime.unit_of_work() as uow:
            uow.session.add_all([
                UserRow(user_id=actor, username_display="p29-requester",
                        username_normalized="p29-requester", state="DISABLED",
                        deployment_role="NONE"),
                UserRow(user_id=system_actor, username_display="p29-system",
                        username_normalized="p29-system", state="DISABLED",
                        deployment_role="NONE"),
                ProjectRow(project_id=project, project_code="P29-SYNTHETIC",
                           project_code_normalized="P29-SYNTHETIC",
                           name="P29 Synthetic Output", created_by=actor),
            ])
            uow.session.flush()
            for index, (job_id, request_id, snapshot_id, source_id,
                        template_id, trace_id, payload) in enumerate(fixture):
                uow.session.add(OutputContextSnapshotRow(
                    context_snapshot_id=snapshot_id, project_id=project,
                    source_version_refs=[str(source_id)],
                    context_payload={"synthetic": True}, context_fingerprint=b"s" * 32,
                    created_by=actor,
                ))
                uow.session.add(JobRow(
                    job_id=job_id, owner_module="output", job_type="OUTPUT_GENERATE",
                    scope="PROJECT", project_id=project, actor_ref=actor,
                    trace_id=str(trace_id), payload_refs=payload,
                    idempotency_key=f"p29-job-{index}", max_attempts=3,
                ))
            uow.session.flush()
            for index, (job_id, request_id, snapshot_id, source_id,
                        template_id, trace_id, payload) in enumerate(fixture):
                uow.session.add(OutputRequestRow(
                    output_request_id=request_id, project_id=project, output_type="DOCX",
                    template_version_ref=template_id,
                    source_version_refs=[str(source_id)], output_policy_ref="p29.synthetic.v1",
                    plugin_operation="word.generate", context_snapshot_id=snapshot_id,
                    input_fingerprint=bytes([index + 1]) * 32, generation_no=1,
                    request_state="QUEUED", job_ref=job_id, current_execution_ref=None,
                    idempotency_key=f"p29-request-{index}", trace_id=trace_id,
                    requested_by=actor, lock_version=0,
                ))
            uow.commit()

        queue = JobLeaseService(unit_of_work=runtime.unit_of_work,
                                repository=SqlAlchemyJobLeaseRepository())
        valid, audit_failure = fixture
        worker = "p29-output-worker"
        claims = {}
        for item in (valid, audit_failure):
            claim = queue.claim_next_output(worker_ref=worker, lease_seconds=300)
            if claim is None or claim.job_id not in {item[0] for item in fixture}:
                raise AssertionError("Output queue did not issue its exact synthetic claim")
            claims[claim.job_id] = claim

        owner = make_owner(runtime, system_actor)
        valid_claim = claims[valid[0]]
        before_valid = snapshot(database_dsn(database, args.port), project, valid[1], valid[0])
        for label, wrong_worker_ref, token, altered in (
            ("wrong worker", "p29-other-worker", valid_claim.fencing_token, valid_claim),
            ("stale token", worker, valid_claim.fencing_token + 1, valid_claim),
            ("wrong request binding", worker, valid_claim.fencing_token,
             ClaimedJob(valid_claim.job_id, valid_claim.job_type, valid_claim.scope,
                        valid_claim.project_id,
                        {**valid_claim.payload_refs, "output_request_id": str(uuid.uuid4())},
                        valid_claim.trace_id, valid_claim.fencing_token, valid_claim.attempt_no)),
        ):
            try:
                owner.start(altered, worker_ref=wrong_worker_ref)
            except OutputGenerationStartError:
                pass
            else:
                raise AssertionError(label + " was accepted")
            if snapshot(database_dsn(database, args.port), project, valid[1], valid[0]) != before_valid:
                raise AssertionError(label + " left partial state or audit rows")

        started = owner.start(valid_claim, worker_ref=worker)
        if (started.state != "GENERATING" or not started.changed
                or started.lock_version != 1 or started.requested_by != actor):
            raise AssertionError("Output generation start did not return expected facts")
        replay = owner.start(valid_claim, worker_ref=worker)
        if replay.state != "GENERATING" or replay.changed:
            raise AssertionError("same fencing token replay was not idempotent")
        final_valid = snapshot(database_dsn(database, args.port), project, valid[1], valid[0])
        if final_valid[0] != ("GENERATING", started.execution_id, 1):
            raise AssertionError("Output state, execution ref or lock version mismatch")
        if final_valid[1][0] != "RUNNING" or final_valid[2] != 1:
            raise AssertionError("lease proof mutated Job state or audit was not atomic")
        with runtime.unit_of_work() as uow:
            event = uow.session.execute(text(
                "SELECT actor_type, actor_id, original_actor_id, before_state, after_state "
                "FROM plm.aud_events WHERE target_object_id=:request "
                "AND action='OUTPUT_GENERATION_STARTED'"
            ), {"request": valid[1]}).one()
        if tuple(event) != ("SYSTEM", system_actor, actor, "QUEUED", "GENERATING"):
            raise AssertionError("SYSTEM Audit attribution or transition facts mismatch")

        failed_claim = claims[audit_failure[0]]
        before_failure = snapshot(database_dsn(database, args.port), project,
                                  audit_failure[1], audit_failure[0])
        try:
            make_owner(runtime, system_actor, failing_audit=True).start(
                failed_claim, worker_ref=worker)
        except OutputGenerationStartError:
            pass
        else:
            raise AssertionError("injected audit failure did not abort start transition")
        if snapshot(database_dsn(database, args.port), project,
                    audit_failure[1], audit_failure[0]) != before_failure:
            raise AssertionError("audit failure left partial Output/Job/Audit data")

        print(json.dumps({
            "status": "PASS_SCOPE_LIMITED",
            "wbs": "OUT-01-A01-P29",
            "output_request_locked_before_job_lease_proof": True,
            "valid_binding_started": True,
            "wrong_worker_denied": True,
            "stale_fencing_token_denied": True,
            "wrong_request_binding_denied": True,
            "system_audit_actor_and_requester_attribution": True,
            "exact_execution_replay_idempotent": True,
            "audit_failure_rolled_back_output_and_audit": True,
            "job_state_mutated_by_lease_proof": False,
            "schema_changed": False, "plugin_executed": False,
            "output_files_generated": False, "customer_data": False,
            "external_api_calls": 0, "runner_drive": "D:",
        }, sort_keys=True))
        return 0
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_db(args.port, database)


if __name__ == "__main__":
    raise SystemExit(main())
