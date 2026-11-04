"""Hosted PostgreSQL integration for Output-specific Job claim isolation."""
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
from sqlalchemy import URL, select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


def database_url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def admin_dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def create_database(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(sql.Identifier(name))
        )


def drop_database(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name))
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

    database = "plm_out_p26_" + args.run_id[-10:]
    created = False
    runtime = None
    try:
        create_database(args.port, database)
        created = True
        upgrade_database(database_url(database, args.port), "head")
        runtime = create_database_runtime(database_url(database, args.port))
        actor_id, project_id = uuid.uuid4(), uuid.uuid4()

        output_one, output_two, output_other, other_owner, general_job = (
            uuid.uuid4() for _ in range(5)
        )
        output_ids = {output_one, output_two}
        non_output_ids = {output_other, other_owner, general_job}
        if len(output_ids | non_output_ids) != 5:
            raise AssertionError("synthetic claim fixture identity collision")
        queued = (
            ("output", "OUTPUT_GENERATE", output_one),
            ("output", "OUTPUT_GENERATE", output_two),
            ("output", "OTHER_JOB", output_other),
            ("audit", "OUTPUT_GENERATE", other_owner),
            ("audit", "AUDIT_EXPORT", general_job),
        )

        with runtime.unit_of_work() as uow:
            uow.session.add(UserRow(
                user_id=actor_id, username_display="synthetic-output-worker",
                username_normalized="synthetic-output-worker",
                state="DISABLED", deployment_role="NONE",
            ))
            uow.session.add(ProjectRow(
                project_id=project_id, project_code="P26-SYNTHETIC",
                project_code_normalized="P26-SYNTHETIC",
                name="Synthetic Output Job Claim", created_by=actor_id,
            ))
            uow.session.flush()
            for owner, kind, job_id in queued:
                uow.session.add(JobRow(
                    job_id=job_id, owner_module=owner, job_type=kind,
                    scope="PROJECT", project_id=project_id, actor_ref=actor_id,
                    trace_id=str(uuid.uuid4()),
                    payload_refs={
                        "output_request_id": str(uuid.uuid4()),
                        "context_snapshot_id": str(uuid.uuid4()),
                        "synthetic_fixture": True,
                    },
                    idempotency_key="p26-" + str(job_id),
                    max_attempts=3,
                ))
            uow.commit()

        leases = JobLeaseService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyJobLeaseRepository(),
        )
        first_output = leases.claim_next_output(
            worker_ref="p26-output-worker", lease_seconds=60,
        )
        if (first_output is None or first_output.job_id not in output_ids
                or first_output.job_type != "OUTPUT_GENERATE"
                or first_output.fencing_token != 1 or first_output.attempt_no != 1):
            raise AssertionError("Output-specific claim did not lease exact Output job")
        remaining_output = output_ids - {first_output.job_id}
        if len(remaining_output) != 1:
            raise AssertionError("Output-specific claim changed an unexpected job")

        generic_claims: set[uuid.UUID] = set()
        while True:
            claim = leases.claim_next(worker_ref="p26-generic-worker", lease_seconds=60)
            if claim is None:
                break
            if claim.job_id not in non_output_ids:
                raise AssertionError("generic claim crossed into OUTPUT_GENERATE owner")
            generic_claims.add(claim.job_id)
            if len(generic_claims) > len(non_output_ids):
                raise AssertionError("generic worker claimed a Job more than once")
        if generic_claims != non_output_ids:
            raise AssertionError("generic claim unexpectedly excluded an unrelated Owner/JobType")

        with runtime.unit_of_work() as uow:
            states = dict(uow.session.execute(
                select(JobRow.job_id, JobRow.state).where(
                    JobRow.job_id.in_(output_ids)
                )
            ).all())
        if states.get(next(iter(remaining_output))) != "PENDING":
            raise AssertionError("generic claim changed the remaining Output Generate job")

        second_output = leases.claim_next_output(
            worker_ref="p26-output-worker", lease_seconds=60,
        )
        if (second_output is None or second_output.job_id not in remaining_output
                or second_output.fencing_token != 1 or second_output.attempt_no != 1):
            raise AssertionError("Output-specific claim failed to acquire remaining Output job")
        if leases.claim_next_output(
                worker_ref="p26-output-worker", lease_seconds=60) is not None:
            raise AssertionError("Output-specific claim acquired a mismatched Owner/JobType")

        result = {
            "status": "PASS_SCOPE_LIMITED",
            "wbs": "OUT-01-A01-P26",
            "customer_data": False,
            "external_api_calls": 0,
            "plugin_executed": False,
            "output_files_generated": False,
            "schema_changed": False,
            "generic_claimed_non_output_jobs": len(generic_claims),
            "output_specific_claimed_output_jobs": 2,
            "generic_left_output_job_pending": True,
            "fencing_tokens_verified": True,
            "database": "temporary synthetic PostgreSQL only",
            "runner_drive": "D:",
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if runtime is not None:
            runtime.engine.dispose()
        if created:
            drop_database(args.port, database)


if __name__ == "__main__":
    raise SystemExit(main())
