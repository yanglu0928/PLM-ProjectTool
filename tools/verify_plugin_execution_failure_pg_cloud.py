"""Run the PLG-03-A07 atomic failure Owner against isolated packaged PostgreSQL."""
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
    FailingAudit, SyntheticOutputAdmission, _admission, _count, _extract_parent_like_smoke,
    _seed,
)
from stage_windows_parent_candidate_cloud import stage_candidate
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, JobLeaseService,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.output.application.job_admission import OutputExecutionAdmission
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureOwner,
)
from plm_assistant.modules.output.application.start_generation import (
    OutputGenerationStartOwner,
)
from plm_assistant.modules.output.infrastructure.fail_generation_repository import (
    SqlAlchemyOutputGenerationFailureRepository,
)
from plm_assistant.modules.output.infrastructure.start_generation_repository import (
    SqlAlchemyOutputGenerationStartRepository,
)
from plm_assistant.modules.plugin.application.execution_failure import (
    PluginExecutionFailureError, PluginExecutionFailureOwner,
)
from plm_assistant.modules.plugin.infrastructure.execution_failure_repository import (
    SqlAlchemyPluginExecutionFailureRepository,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.plugin.application.execution_admission import (
    AdmitPluginExecutionCommand, PluginExecutionAdmissionOwner,
)
from plm_assistant.modules.plugin.application.execution_start import (
    PluginExecutionStartError, PluginExecutionStartOwner, StartPluginExecutionCommand,
)
from plm_assistant.modules.plugin.infrastructure.execution_admission_repository import (
    SqlAlchemyPluginExecutionAdmissionRepository,
)
from plm_assistant.modules.plugin.infrastructure.execution_start_repository import (
    SqlAlchemyPluginExecutionStartRepository,
)


def _checked(args: list[str], timeout: int = 180) -> None:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", timeout=timeout, check=False)
    if result.returncode:
        safe = Path(args[0]).name
        raise RuntimeError(f"{safe} failed with exit {result.returncode}")


def _one(engine, sql: str, values: dict):
    with engine.connect() as conn:
        return conn.execute(text(sql), values).one()


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
        raise ValueError("A07 requires a new owned D-drive hosted Windows temp root")
    root.mkdir()
    stage = runner / ("plg03-a07-stage-" + run_id)
    port_sock = socket.socket()
    port_sock.bind(("127.0.0.1", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()
    data_dir, pg_log = root / "pgdata", root / "postgres.log"
    staged = start_attempted = created_database = False
    engine = None
    database = "plm_plg03a07_" + run_id[-10:]
    summary = {}
    try:
        receipt = stage_candidate(args.archive, args.verification_summary, stage)
        staged = True
        if (receipt.get("status") != "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED"
                or receipt.get("installation_performed") is not False
                or receipt.get("services_started") is not False
                or stage.parent.resolve(strict=True) != runner):
            raise ValueError("A07 non-release parent staging receipt rejected")
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
        created_database = True
        url = URL.create("postgresql+psycopg", username="postgres",
                         host="127.0.0.1", port=port, database=database)
        with psycopg.connect(
            f"postgresql://postgres@127.0.0.1:{port}/{database}", autocommit=True,
        ) as conn:
            conn.execute("CREATE EXTENSION vector")
        upgrade_database(url)
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
        jobs = JobLeaseService(
            unit_of_work=make_uow, repository=SqlAlchemyJobLeaseRepository(),
        )
        output_start = OutputGenerationStartOwner(
            unit_of_work=make_uow, jobs=jobs,
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
            raise AssertionError("A07 fixture did not begin at PENDING")
        owner_repo = SqlAlchemyPluginExecutionStartRepository()
        audit = AuditService(SqlAlchemyAuditRepository())
        start_owner = PluginExecutionStartOwner(
            unit_of_work=make_uow, jobs=jobs, repository=owner_repo, audit=audit,
        )
        start_owner.start(StartPluginExecutionCommand(claim, worker))

        output_failure = OutputGenerationFailureOwner(
            unit_of_work=make_uow, jobs=jobs,
            repository=SqlAlchemyOutputGenerationFailureRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            system_actor_id=ids["user"],
        )
        failure_repo = SqlAlchemyPluginExecutionFailureRepository()
        failure_audit = AuditService(SqlAlchemyAuditRepository())
        failure_owner = PluginExecutionFailureOwner(
            unit_of_work=make_uow, output_failure=output_failure,
            repository=failure_repo, audit=failure_audit,
        )
        failed_audit_owner = PluginExecutionFailureOwner(
            unit_of_work=make_uow, output_failure=output_failure,
            repository=failure_repo, audit=FailingAudit(),
        )

        def state_snapshot():
            plugin = _one(engine,
                "SELECT execution_state,lock_version,error_code,retryable,completed_at "
                "FROM plm.plg_executions WHERE plugin_execution_id=:id",
                {"id": admitted.plugin_execution_id})
            output = _one(engine,
                "SELECT request_state,lock_version,completed_at FROM plm.out_output_requests "
                "WHERE output_request_id=:id", {"id": ids["request"]})
            job = _one(engine,
                "SELECT state,completed_at,lease_expires_at FROM plm.job_jobs WHERE job_id=:id",
                {"id": ids["job"]})
            lease = _one(engine,
                "SELECT state FROM plm.job_leases WHERE job_id=:id", {"id": ids["job"]})
            attempt = _one(engine,
                "SELECT completed_at,error_code FROM plm.job_attempts WHERE job_id=:id",
                {"id": ids["job"]})
            events = _count(engine,
                "SELECT count(*) FROM plm.plg_execution_state_events "
                "WHERE plugin_execution_id=:id AND from_state='RUNNING' AND to_state='FAILED'",
                {"id": admitted.plugin_execution_id})
            output_audit = _count(engine,
                "SELECT count(*) FROM plm.aud_events WHERE target_object_id=:id "
                "AND action='OUTPUT_GENERATION_FAILED'", {"id": ids["request"]})
            plugin_audit = _count(engine,
                "SELECT count(*) FROM plm.aud_events WHERE target_object_id=:id "
                "AND action='PLUGIN_EXECUTION_FAILED'", {"id": admitted.plugin_execution_id})
            return plugin, output, job, lease, attempt, events, output_audit, plugin_audit

        before = state_snapshot()
        try:
            failed_audit_owner.fail(claim, worker_ref=worker,
                                    error_code="OUTPUT_PLUGIN_UNAVAILABLE")
        except PluginExecutionFailureError:
            pass
        else:
            raise AssertionError("synthetic Plugin Audit failure did not fail closed")
        if state_snapshot() != before:
            raise AssertionError("Plugin Audit failure did not roll back Output/Job/Plugin")

        for bad_claim, bad_worker, bad_code in (
            (ClaimedJob(claim.job_id, claim.job_type, claim.scope, claim.project_id,
                        claim.payload_refs, claim.trace_id, claim.fencing_token - 1,
                        claim.attempt_no), worker, "OUTPUT_GENERATION_FAILED"),
            (claim, "wrong.worker", "OUTPUT_GENERATION_FAILED"),
            (claim, worker, "sensitive stack trace"),
        ):
            snapshot_before = state_snapshot()
            try:
                failure_owner.fail(bad_claim, worker_ref=bad_worker, error_code=bad_code)
            except PluginExecutionFailureError:
                pass
            else:
                raise AssertionError("invalid A07 failure request was accepted")
            if state_snapshot() != snapshot_before:
                raise AssertionError("rejected A07 failure caused partial writes")

        result = failure_owner.fail(
            claim, worker_ref=worker, error_code="OUTPUT_PLUGIN_UNAVAILABLE",
        )
        if not result.changed or result.execution_state != "FAILED":
            raise AssertionError("current claim did not fail PluginExecution")
        after = state_snapshot()
        plugin, output, job, lease, attempt, events, output_audits, plugin_audits = after
        if (plugin.execution_state != "FAILED" or plugin.error_code != "OUTPUT_PLUGIN_UNAVAILABLE"
                or plugin.retryable is not False or plugin.completed_at is None
                or plugin.lock_version != 2):
            raise AssertionError("PluginExecution FAILED facts were not atomically persisted")
        if (output.request_state != "FAILED" or output.completed_at is None
                or output.lock_version != 2):
            raise AssertionError("OutputRequest did not fail in the same UoW")
        if (job.state != "FAILED" or job.completed_at is None
                or job.lease_expires_at is not None or lease.state != "RELEASED"
                or attempt.completed_at is None
                or attempt.error_code != "OUTPUT_PLUGIN_UNAVAILABLE"):
            raise AssertionError("Job/lease/attempt did not fail non-retryably")
        if (events, output_audits, plugin_audits) != (1, 1, 1):
            raise AssertionError("A07 state event or owner Audit count was not exactly one")
        event_reason = _one(engine,
            "SELECT reason_code FROM plm.plg_execution_state_events "
            "WHERE plugin_execution_id=:id AND to_state='FAILED'",
            {"id": admitted.plugin_execution_id}).reason_code
        if event_reason != "OUTPUT_PLUGIN_UNAVAILABLE":
            raise AssertionError("failure reason code was not fixed and allowlisted")

        summary = {
            "status": "PASS_SCOPE_LIMITED", "wbs": "PLG-03-A07",
            "runtime": "GitHub Hosted Windows Server 2025 D-drive temporary packaged PG18.6",
            "transition": "RUNNING PluginExecution, OutputRequest and Job atomically FAILED with one plugin event and per-owner Audit",
            "audit_failure": "Plugin Audit failure rolls back Output, Job lease/attempt, Plugin root and event",
            "invalid_claims": "stale fence, wrong worker and non-allowlisted error rejected with zero writes",
            "retryable": False, "plugin_process_started": False,
            "worker_wired": False, "customer_data": False, "external_calls": 0,
            "formal_trust": False, "release_eligible": False,
            "parent_archive_sha256": receipt["archive_sha256"],
            "source_commit": os.environ.get("GITHUB_SHA", ""),
            "workflow_run": run_id,
        }
        print("PLG_03_A07_PG18_PASS " + json.dumps(summary, sort_keys=True))
    finally:
        if engine is not None:
            engine.dispose()
        if created_database:
            with psycopg.connect(f"postgresql://postgres@127.0.0.1:{port}/postgres",
                                 autocommit=True) as conn:
                conn.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (database,))
                conn.execute(f'DROP DATABASE IF EXISTS "{database}"')
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
                if resolved.parent != runner or owned.is_symlink() or resolved.drive.upper() == "C:":
                    raise RuntimeError("refusing cleanup outside owned D-drive temp")
                shutil.rmtree(owned)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n",
                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
