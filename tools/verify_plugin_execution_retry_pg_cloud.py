"""Validate per-attempt PluginExecution retries with isolated packaged PostgreSQL."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/backend/src"))

import psycopg
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import sessionmaker

from tools.verify_plugin_execution_admission_pg_cloud import (
    FailingAudit, SyntheticOutputAdmission, _admission, _count,
    _extract_parent_like_smoke, _seed,
)
from stage_windows_parent_candidate_cloud import stage_candidate
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.output.application.retry_generation import OutputGenerationRetryOwner
from plm_assistant.modules.output.application.start_generation import OutputGenerationStartOwner
from plm_assistant.modules.output.infrastructure.retry_generation_repository import (
    SqlAlchemyOutputGenerationRetryRepository,
)
from plm_assistant.modules.output.infrastructure.start_generation_repository import (
    SqlAlchemyOutputGenerationStartRepository,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import (
    downgrade_database, upgrade_database,
)
from plm_assistant.modules.plugin.application.execution_admission import (
    AdmitPluginExecutionCommand, PluginExecutionAdmissionOwner,
)
from plm_assistant.modules.plugin.application.execution_retry import (
    PluginExecutionRetryError, PluginExecutionRetryOwner,
)
from plm_assistant.modules.plugin.application.execution_start import (
    PluginExecutionStartOwner, StartPluginExecutionCommand,
)
from plm_assistant.modules.plugin.infrastructure.execution_admission_repository import (
    SqlAlchemyPluginExecutionAdmissionRepository,
)
from plm_assistant.modules.plugin.infrastructure.execution_retry_repository import (
    SqlAlchemyPluginExecutionRetryRepository,
)
from plm_assistant.modules.plugin.infrastructure.execution_start_repository import (
    SqlAlchemyPluginExecutionStartRepository,
)


def _checked(args: list[str], timeout: int = 180) -> None:
    result = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed with exit {result.returncode}")


def _one(engine, sql: str, values: dict):
    with engine.connect() as conn:
        return conn.execute(text(sql), values).one()


def _empty_migration_rehearsal(url: URL) -> None:
    upgrade_database(url, "20261105_0232")
    upgrade_database(url)
    engine = create_engine(url)
    try:
        count = _count(
            engine,
            "SELECT count(*) FROM pg_constraint WHERE conname='uq_plg_executions__job_attempt'",
            {},
        )
        if count != 1:
            raise AssertionError("empty migration upgrade did not install per-attempt unique key")
        downgrade_database(url, "20261105_0232")
        upgrade_database(url)
        count = _count(
            engine,
            "SELECT count(*) FROM pg_constraint WHERE conname='uq_plg_executions__job_attempt'",
            {},
        )
        if count != 1:
            raise AssertionError("empty migration re-upgrade did not restore the unique key")
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--verification-summary", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()
    runner = Path(os.environ.get("RUNNER_TEMP", "")).resolve(strict=True)
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    root = args.run_root
    if (sys.platform != "win32" or runner.drive.upper() != "D:"
            or root.parent.resolve(strict=True) != runner or root.exists()
            or root.is_symlink() or not run_id.isascii() or not run_id.isdigit()):
        raise ValueError("A08 requires a new owned D-drive hosted Windows temp root")
    root.mkdir()
    stage = runner / ("plg03-a08-stage-" + run_id)
    port_sock = socket.socket()
    port_sock.bind(("127.0.0.1", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()
    data_dir, pg_log = root / "pgdata", root / "postgres.log"
    staged = start_attempted = created_database = created_empty_database = False
    engine = None
    database = "plm_plg03a08_" + run_id[-10:]
    empty_database = database + "_empty"
    summary: dict = {}
    try:
        receipt = stage_candidate(args.archive, args.verification_summary, stage)
        staged = True
        if (receipt.get("status") != "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED"
                or receipt.get("installation_performed") is not False
                or receipt.get("services_started") is not False
                or stage.parent.resolve(strict=True) != runner):
            raise ValueError("A08 non-release parent staging receipt rejected")
        shutil.rmtree(stage)
        staged = False
        _extract_parent_like_smoke(args.archive, root, receipt["archive_sha256"])
        pg_bin = root / "payload" / "pgsql" / "bin"
        initdb, pg_ctl = pg_bin / "initdb.exe", pg_bin / "pg_ctl.exe"
        if any(p.is_symlink() or not p.is_file() for p in (initdb, pg_ctl)):
            raise ValueError("verified packaged PG18 runtime missing")
        _checked([str(initdb), "-D", str(data_dir), "-U", "postgres",
                  "--auth-local=trust", "--auth-host=trust", "--no-locale", "-E", "UTF8"])
        start_attempted = True
        start_log = root / "pgctl-start.txt"
        with start_log.open("w", encoding="utf-8") as output:
            proc = subprocess.run(
                [str(pg_ctl), "-D", str(data_dir), "-l", str(pg_log),
                 "-o", f"-h 127.0.0.1 -p {port} -c listen_addresses=127.0.0.1",
                 "-w", "start"],
                stdout=output, stderr=subprocess.STDOUT, text=True,
                timeout=180, check=False,
            )
        if proc.returncode:
            raise RuntimeError(f"packaged temporary PostgreSQL start failed ({proc.returncode})")
        admin_dsn = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{database}"')
            conn.execute(f'CREATE DATABASE "{empty_database}"')
        created_database = created_empty_database = True
        for db_name in (database, empty_database):
            with psycopg.connect(
                f"postgresql://postgres@127.0.0.1:{port}/{db_name}", autocommit=True,
            ) as conn:
                conn.execute("CREATE EXTENSION vector")
        empty_url = URL.create(
            "postgresql+psycopg", username="postgres", host="127.0.0.1",
            port=port, database=empty_database,
        )
        _empty_migration_rehearsal(empty_url)

        url = URL.create("postgresql+psycopg", username="postgres",
                         host="127.0.0.1", port=port, database=database)
        upgrade_database(url, "20261105_0232")
        engine = create_engine(url)
        session_factory = sessionmaker(engine, expire_on_commit=False)
        make_uow = lambda: SqlAlchemyUnitOfWork(session_factory)
        ids = {key: uuid.uuid4() for key in
               ("user", "project", "job", "context", "request", "trace",
                "package", "install")}
        worker, operation = "synthetic.worker", "synthetic.start.generate"
        _seed(
            engine, user_id=ids["user"], project_id=ids["project"],
            job_id=ids["job"], context_id=ids["context"], request_id=ids["request"],
            package_id=ids["package"], install_id=ids["install"],
            trace_id=ids["trace"], worker=worker, operation=operation,
            seed_plugin=True,
        )
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE plm.job_jobs SET max_attempts=2 WHERE job_id=:id"
            ), {"id": ids["job"]})
        upgrade_database(url)

        claim = ClaimedJob(
            job_id=ids["job"], job_type="OUTPUT_GENERATE", scope="PROJECT",
            project_id=ids["project"],
            payload_refs={"output_request_id": str(ids["request"]),
                          "context_snapshot_id": str(ids["context"])},
            trace_id=str(ids["trace"]), fencing_token=19, attempt_no=1,
        )
        fact = _admission(
            job_id=ids["job"], project_id=ids["project"],
            request_id=ids["request"], context_id=ids["context"],
            operation=operation,
        )
        lease_repository = SqlAlchemyJobLeaseRepository()
        jobs = JobLeaseService(unit_of_work=make_uow, repository=lease_repository)
        output_start = OutputGenerationStartOwner(
            unit_of_work=make_uow, jobs=lease_repository,
            repository=SqlAlchemyOutputGenerationStartRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            system_actor_id=ids["user"],
        )
        output_start.start(claim, worker_ref=worker)
        admission_repo = SqlAlchemyPluginExecutionAdmissionRepository()
        admission_owner = PluginExecutionAdmissionOwner(
            unit_of_work=make_uow, jobs=jobs,
            output_admission=SyntheticOutputAdmission({claim.job_id: fact}),
            targets=admission_repo, repository=admission_repo,
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        admitted = admission_owner.admit(AdmitPluginExecutionCommand(claim, worker))
        if not admitted.created or admitted.execution_state != "PENDING":
            raise AssertionError("A08 attempt-one fixture did not begin at PENDING")
        start_owner = PluginExecutionStartOwner(
            unit_of_work=make_uow, jobs=jobs,
            repository=SqlAlchemyPluginExecutionStartRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        start_owner.start(StartPluginExecutionCommand(claim, worker))

        output_retry = OutputGenerationRetryOwner(
            unit_of_work=make_uow, jobs=lease_repository,
            repository=SqlAlchemyOutputGenerationRetryRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            system_actor_id=ids["user"],
        )
        retry_owner = PluginExecutionRetryOwner(
            unit_of_work=make_uow, output_retry=output_retry,
            repository=SqlAlchemyPluginExecutionRetryRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        failed_audit_owner = PluginExecutionRetryOwner(
            unit_of_work=make_uow, output_retry=output_retry,
            repository=SqlAlchemyPluginExecutionRetryRepository(),
            audit=FailingAudit(),
        )

        def state_snapshot(current_claim, execution_id):
            plugin = _one(
                engine,
                "SELECT execution_state,lock_version,error_code,retryable,completed_at "
                "FROM plm.plg_executions WHERE plugin_execution_id=:id",
                {"id": execution_id},
            )
            output = _one(
                engine,
                "SELECT request_state,lock_version,completed_at,current_execution_ref "
                "FROM plm.out_output_requests WHERE output_request_id=:id",
                {"id": ids["request"]},
            )
            job = _one(
                engine,
                "SELECT state,completed_at,lease_expires_at,attempt_count "
                "FROM plm.job_jobs WHERE job_id=:id",
                {"id": ids["job"]},
            )
            lease = _one(
                engine,
                "SELECT state FROM plm.job_leases WHERE job_id=:id AND fencing_token=:token",
                {"id": ids["job"], "token": current_claim.fencing_token},
            )
            attempt = _one(
                engine,
                "SELECT completed_at,error_code FROM plm.job_attempts "
                "WHERE job_id=:id AND attempt_no=:attempt",
                {"id": ids["job"], "attempt": current_claim.attempt_no},
            )
            events = _count(
                engine,
                "SELECT count(*) FROM plm.plg_execution_state_events "
                "WHERE plugin_execution_id=:id AND from_state='RUNNING' AND to_state='FAILED'",
                {"id": execution_id},
            )
            output_audits = _count(
                engine,
                "SELECT count(*) FROM plm.aud_events WHERE target_object_id=:id "
                "AND action IN ('OUTPUT_GENERATION_RETRY_SCHEDULED',"
                "'OUTPUT_GENERATION_RETRY_EXHAUSTED')",
                {"id": ids["request"]},
            )
            plugin_audits = _count(
                engine,
                "SELECT count(*) FROM plm.aud_events WHERE target_object_id=:id "
                "AND action IN ('PLUGIN_EXECUTION_RETRY_SCHEDULED',"
                "'PLUGIN_EXECUTION_RETRY_EXHAUSTED')",
                {"id": execution_id},
            )
            return plugin, output, job, lease, attempt, events, output_audits, plugin_audits

        before = state_snapshot(claim, admitted.plugin_execution_id)
        try:
            failed_audit_owner.retry(
                claim, worker_ref=worker, error_code="OUTPUT_PLUGIN_BUSY",
            )
        except PluginExecutionRetryError:
            pass
        else:
            raise AssertionError("synthetic Plugin Audit failure did not fail closed")
        if state_snapshot(claim, admitted.plugin_execution_id) != before:
            raise AssertionError("Plugin Audit failure did not roll back Output/Job/Plugin")

        for bad_claim, bad_worker, bad_code in (
            (ClaimedJob(claim.job_id, claim.job_type, claim.scope, claim.project_id,
                        claim.payload_refs, claim.trace_id, claim.fencing_token - 1,
                        claim.attempt_no), worker, "OUTPUT_PLUGIN_BUSY"),
            (claim, "wrong.worker", "OUTPUT_PLUGIN_BUSY"),
            (claim, worker, "OUTPUT_PLUGIN_UNAVAILABLE"),
        ):
            snapshot_before = state_snapshot(claim, admitted.plugin_execution_id)
            try:
                retry_owner.retry(bad_claim, worker_ref=bad_worker, error_code=bad_code)
            except PluginExecutionRetryError:
                pass
            else:
                raise AssertionError("invalid A08 retry request was accepted")
            if state_snapshot(claim, admitted.plugin_execution_id) != snapshot_before:
                raise AssertionError("rejected A08 retry caused partial writes")

        first = retry_owner.retry(
            claim, worker_ref=worker, error_code="OUTPUT_PLUGIN_BUSY",
        )
        if (first.job_state != "RETRY_WAIT" or first.output_state != "QUEUED"
                or first.retry_delay_seconds <= 0
                or first.facts.execution_state != "FAILED"):
            raise AssertionError("attempt-one transient failure did not schedule retry")
        first_state = state_snapshot(claim, admitted.plugin_execution_id)
        plugin, output, job, lease, attempt, events, output_audits, plugin_audits = first_state
        if (plugin.execution_state != "FAILED" or plugin.error_code != "OUTPUT_PLUGIN_BUSY"
                or plugin.retryable is not True or plugin.completed_at is None
                or plugin.lock_version != 2):
            raise AssertionError("attempt-one Plugin failure facts were not persisted")
        if (output.request_state != "QUEUED" or output.completed_at is not None
                or output.current_execution_ref is not None or output.lock_version != 2):
            raise AssertionError("Output was not requeued atomically")
        if (job.state != "RETRY_WAIT" or job.completed_at is not None
                or job.lease_expires_at is not None or job.attempt_count != 1
                or lease.state != "RELEASED" or attempt.completed_at is None
                or attempt.error_code != "OUTPUT_PLUGIN_BUSY"):
            raise AssertionError("Job/lease/attempt did not enter retry wait")
        if (events, output_audits, plugin_audits) != (1, 1, 1):
            raise AssertionError("attempt-one event or retry Audit was not exactly one")

        # Prove reversible down/up with one historical attempt before creating attempt two.
        downgrade_database(url, "20261105_0232")
        if _count(engine, "SELECT count(*) FROM plm.plg_executions WHERE job_id=:id",
                  {"id": ids["job"]}) != 1:
            raise AssertionError("single-attempt downgrade did not preserve history")
        upgrade_database(url)
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE plm.job_jobs SET available_at=statement_timestamp()-interval '1 second' "
                "WHERE job_id=:id"
            ), {"id": ids["job"]})
        second_claim = jobs.claim_next_output(worker_ref=worker, lease_seconds=300)
        if (second_claim is None or second_claim.job_id != ids["job"]
                or second_claim.attempt_no != 2
                or second_claim.fencing_token <= claim.fencing_token):
            raise AssertionError("Jobs did not issue a fresh second attempt/fence")
        output_start.start(second_claim, worker_ref=worker)
        second_admitted = admission_owner.admit(
            AdmitPluginExecutionCommand(second_claim, worker),
        )
        if (not second_admitted.created or second_admitted.execution_state != "PENDING"
                or second_admitted.plugin_execution_id == admitted.plugin_execution_id):
            raise AssertionError("attempt two did not receive an independent execution root")
        start_owner.start(StartPluginExecutionCommand(second_claim, worker))
        exhausted = retry_owner.retry(
            second_claim, worker_ref=worker, error_code="OUTPUT_PLUGIN_BUSY",
        )
        if (exhausted.job_state != "FAILED" or exhausted.output_state != "FAILED"
                or exhausted.retry_delay_seconds != 0
                or exhausted.facts.attempt_no != 2):
            raise AssertionError("maximum-attempt exhaustion did not fail closed")
        second_state = state_snapshot(second_claim, second_admitted.plugin_execution_id)
        plugin2, output2, job2, lease2, attempt2, events2, output_audits2, plugin_audits2 = second_state
        if (plugin2.execution_state != "FAILED" or plugin2.retryable is not True
                or plugin2.error_code != "OUTPUT_PLUGIN_BUSY" or plugin2.completed_at is None):
            raise AssertionError("exhausted PluginExecution retry history missing")
        if (output2.request_state != "FAILED" or output2.completed_at is None
                or job2.state != "FAILED" or job2.completed_at is None
                or lease2.state != "RELEASED" or attempt2.completed_at is None):
            raise AssertionError("attempt exhaustion did not atomically fail Output/Job")
        history = _one(
            engine,
            "SELECT count(*) AS total, count(DISTINCT attempt_no) AS attempts "
            "FROM plm.plg_executions WHERE job_id=:id",
            {"id": ids["job"]},
        )
        keys = _count(
            engine,
            "SELECT count(DISTINCT idempotency_key) FROM plm.plg_executions WHERE job_id=:id",
            {"id": ids["job"]},
        )
        if (history.total, history.attempts, keys) != (2, 2, 2):
            raise AssertionError("per-attempt PluginExecution history/idempotency was not preserved")
        # Down must reject, and preserve both rows, when the legacy per-job key cannot be restored.
        try:
            downgrade_database(url, "20261105_0232")
        except Exception:
            pass
        else:
            raise AssertionError("down migration accepted multiple attempts for one Job")
        head = _one(engine, "SELECT version_num FROM alembic_version", {}).version_num
        preserved = _count(
            engine, "SELECT count(*) FROM plm.plg_executions WHERE job_id=:id",
            {"id": ids["job"]},
        )
        if head != "20261106_0233" or preserved != 2:
            raise AssertionError("guarded downgrade changed head or deleted attempt history")

        summary = {
            "status": "PASS_SCOPE_LIMITED", "wbs": "PLG-03-A08",
            "runtime": "GitHub Hosted Windows Server 2025 D-drive temporary packaged PG18.6",
            "migration": "empty and populated 0232-to-0233 up/down/up; populated multi-attempt down safely rejected",
            "retry": "attempt one schedules RETRY_WAIT/QUEUED; attempt two reaches max and fails Job/Output",
            "attempt_history": "two distinct PluginExecution roots, attempt numbers and idempotency keys retained",
            "audit_failure": "Plugin Audit failure rolls back Output/Job/lease/attempt/Plugin root/event",
            "invalid_claims": "stale fence, wrong worker and non-allowlisted error rejected with zero writes",
            "plugin_process_started": False, "worker_wired": False,
            "customer_data": False, "external_calls": 0,
            "formal_trust": False, "release_eligible": False,
            "parent_archive_sha256": receipt["archive_sha256"],
            "source_commit": os.environ.get("GITHUB_SHA", ""),
            "workflow_run": run_id,
        }
        summary_out = args.summary_out.resolve()
        if summary_out.parent != runner or summary_out.exists():
            raise ValueError("A08 summary output is outside the owned runner temp boundary")
        summary_out.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
        print("PLG_03_A08_PG18_PASS " + json.dumps(summary, sort_keys=True))
    finally:
        if engine is not None:
            engine.dispose()
        if created_database or created_empty_database:
            with psycopg.connect(f"postgresql://postgres@127.0.0.1:{port}/postgres",
                                 autocommit=True) as conn:
                for db_name, created in ((database, created_database),
                                         (empty_database, created_empty_database)):
                    if created:
                        conn.execute(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname=%s AND pid<>pg_backend_pid()", (db_name,))
                        conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        if start_attempted:
            pg_ctl = root / "payload" / "pgsql" / "bin" / "pg_ctl.exe"
            status = subprocess.run(
                [str(pg_ctl), "-D", str(data_dir), "status"],
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, timeout=20, check=False,
            )
            if status.returncode == 0:
                with (root / "pgctl-stop.txt").open("w", encoding="utf-8") as output:
                    stop = subprocess.run(
                        [str(pg_ctl), "-D", str(data_dir), "-m", "fast", "-w", "stop"],
                        stdout=output, stderr=subprocess.STDOUT, text=True,
                        timeout=180, check=False,
                    )
                if stop.returncode:
                    raise RuntimeError("temporary PostgreSQL shutdown was not confirmed")
            elif status.returncode != 3:
                raise RuntimeError("temporary PostgreSQL status was not confirmed")
        for owned in (stage, root):
            if owned.exists():
                resolved = owned.resolve(strict=True)
                if resolved.parent != runner:
                    raise ValueError("refusing cleanup outside the owned runner temp boundary")
                shutil.rmtree(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
