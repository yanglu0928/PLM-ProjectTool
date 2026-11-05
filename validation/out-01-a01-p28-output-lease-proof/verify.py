"""Hosted PostgreSQL proof for current Output claim fencing."""
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
from sqlalchemy import URL, func, text, update

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobLeaseRow, JobRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


def db_url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def admin_dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def create_database(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(
            sql.Identifier(name)))


def drop_database(port: int, name: str) -> None:
    with psycopg.connect(admin_dsn(port), autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(name)))


def expect_rejected(call, label: str) -> None:
    try:
        call()
    except JobLeaseError as exc:
        if exc.code not in {"STALE_LEASE", "INCONSISTENT_LEASE"}:
            raise AssertionError(label + " returned an unexpected error") from None
        return
    raise AssertionError(label + " was accepted")


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

    database = "plm_out_p28_" + args.run_id[-10:]
    created, runtime = False, None
    try:
        create_database(args.port, database)
        created = True
        upgrade_database(db_url(database, args.port), "head")
        runtime = create_database_runtime(db_url(database, args.port))
        actor, project = uuid.uuid4(), uuid.uuid4()
        output_job, other_job = uuid.uuid4(), uuid.uuid4()
        with runtime.unit_of_work() as uow:
            uow.session.add(UserRow(
                user_id=actor, username_display="p28-synthetic",
                username_normalized="p28-synthetic", state="DISABLED",
                deployment_role="NONE",
            ))
            uow.session.add(ProjectRow(
                project_id=project, project_code="P28-SYNTHETIC",
                project_code_normalized="P28-SYNTHETIC",
                name="P28 Synthetic Lease", created_by=actor,
            ))
            uow.session.flush()
            for job_id, owner in ((output_job, "output"), (other_job, "audit")):
                uow.session.add(JobRow(
                    job_id=job_id, owner_module=owner, job_type="OUTPUT_GENERATE",
                    scope="PROJECT", project_id=project, actor_ref=actor,
                    trace_id=str(uuid.uuid4()),
                    payload_refs={"synthetic_fixture": True},
                    idempotency_key="p28-" + str(job_id), max_attempts=3,
                ))
            uow.commit()

        service = JobLeaseService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyJobLeaseRepository(),
        )
        claim = service.claim_next_output(
            worker_ref="p28-output-worker", lease_seconds=90,
        )
        if claim is None or claim.job_id != output_job:
            raise AssertionError("Output-specific claim was not issued")
        proof = service.check_output_claim(
            job_id=claim.job_id, fencing_token=claim.fencing_token,
            worker_ref="p28-output-worker",
        )
        if (proof.job_id != output_job or proof.job_type != "OUTPUT_GENERATE"
                or proof.fencing_token != claim.fencing_token
                or proof.attempt_no != claim.attempt_no):
            raise AssertionError("active Output lease proof does not match claim")

        expect_rejected(
            lambda: service.check_output_claim(
                job_id=claim.job_id, fencing_token=claim.fencing_token,
                worker_ref="p28-wrong-worker",
            ), "wrong worker",
        )
        expect_rejected(
            lambda: service.check_output_claim(
                job_id=claim.job_id, fencing_token=claim.fencing_token + 1,
                worker_ref="p28-output-worker",
            ), "stale fencing token",
        )

        other = service.claim_next(worker_ref="p28-generic-worker", lease_seconds=90)
        if other is None or other.job_id != other_job:
            raise AssertionError("generic fixture job was not acquired")
        expect_rejected(
            lambda: service.check_output_claim(
                job_id=other.job_id, fencing_token=other.fencing_token,
                worker_ref="p28-generic-worker",
            ), "non-Output Owner",
        )

        past = func.statement_timestamp() - text("INTERVAL '1 second'")
        with runtime.unit_of_work() as uow:
            uow.session.execute(
                update(JobRow).where(JobRow.job_id == output_job)
                .values(lease_expires_at=past)
            )
            uow.session.execute(
                update(JobLeaseRow).where(
                    JobLeaseRow.job_id == output_job,
                    JobLeaseRow.fencing_token == claim.fencing_token,
                ).values(lease_expires_at=past)
            )
            uow.commit()
        expect_rejected(
            lambda: service.check_output_claim(
                job_id=output_job, fencing_token=claim.fencing_token,
                worker_ref="p28-output-worker",
            ), "expired lease",
        )

        print(json.dumps({
            "status": "PASS_SCOPE_LIMITED",
            "wbs": "OUT-01-A01-P28",
            "active_output_claim_proof": True,
            "wrong_worker_denied": True,
            "stale_fencing_token_denied": True,
            "other_owner_denied": True,
            "expired_lease_denied": True,
            "job_state_mutated_by_proof": False,
            "customer_data": False, "external_api_calls": 0,
            "plugin_executed": False, "output_files_generated": False,
            "schema_changed": False, "runner_drive": "D:",
        }, sort_keys=True))
        return 0
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            drop_database(args.port, database)


if __name__ == "__main__":
    raise SystemExit(main())
