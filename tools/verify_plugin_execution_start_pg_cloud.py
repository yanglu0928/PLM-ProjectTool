"""Run the PLG-03-A06 state-start Owner against isolated packaged PostgreSQL."""
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
        raise ValueError("A06 requires a new owned D-drive hosted Windows temp root")
    root.mkdir()
    stage = runner / ("plg03-a06-stage-" + run_id)
    port_sock = socket.socket()
    port_sock.bind(("127.0.0.1", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()
    data_dir, pg_log = root / "pgdata", root / "postgres.log"
    staged = start_attempted = created_database = False
    engine = None
    database = "plm_plg03a06_" + run_id[-10:]
    summary = {}
    try:
        receipt = stage_candidate(args.archive, args.verification_summary, stage)
        staged = True
        if (receipt.get("status") != "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED"
                or receipt.get("installation_performed") is not False
                or receipt.get("services_started") is not False
                or stage.parent.resolve(strict=True) != runner):
            raise ValueError("A06 non-release parent staging receipt rejected")
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
        admission_repo = SqlAlchemyPluginExecutionAdmissionRepository()
        admission_owner = PluginExecutionAdmissionOwner(
            unit_of_work=make_uow, jobs=jobs,
            output_admission=SyntheticOutputAdmission({claim.job_id: fact}),
            targets=admission_repo, repository=admission_repo,
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        admitted = admission_owner.admit(AdmitPluginExecutionCommand(claim, worker))
        if not admitted.created or admitted.execution_state != "PENDING":
            raise AssertionError("A06 fixture did not begin at PENDING")
        owner_repo = SqlAlchemyPluginExecutionStartRepository()
        audit = AuditService(SqlAlchemyAuditRepository())
        owner = PluginExecutionStartOwner(
            unit_of_work=make_uow, jobs=jobs, repository=owner_repo, audit=audit,
        )

        failing_owner = PluginExecutionStartOwner(
            unit_of_work=make_uow, jobs=jobs, repository=owner_repo,
            audit=FailingAudit(),
        )
        try:
            failing_owner.start(StartPluginExecutionCommand(claim, worker))
        except PluginExecutionStartError:
            pass
        else:
            raise AssertionError("synthetic Audit failure did not fail closed")
        row = engine.connect().execute(text(
            "SELECT execution_state, started_at, lock_version FROM plm.plg_executions "
            "WHERE plugin_execution_id=:id"
        ), {"id": admitted.plugin_execution_id}).one()
        if row.execution_state != "PENDING" or row.started_at is not None or row.lock_version != 0:
            raise AssertionError("Audit failure did not roll back PENDING root update")
        if _count(engine,
                  "SELECT count(*) FROM plm.plg_execution_state_events "
                  "WHERE plugin_execution_id=:id AND to_state='RUNNING'",
                  {"id": admitted.plugin_execution_id}) != 0:
            raise AssertionError("Audit failure left a RUNNING state event")

        first = owner.start(StartPluginExecutionCommand(claim, worker))
        if not first.changed or first.execution_state != "RUNNING":
            raise AssertionError("current lease did not transition PENDING to RUNNING")
        running = engine.connect().execute(text(
            "SELECT execution_state, started_at, lock_version FROM plm.plg_executions "
            "WHERE plugin_execution_id=:id"
        ), {"id": admitted.plugin_execution_id}).one()
        if running.execution_state != "RUNNING" or running.started_at is None or running.lock_version != 1:
            raise AssertionError("RUNNING root state/started_at/version was not persisted")
        counts = (
            _count(engine,
                "SELECT count(*) FROM plm.plg_execution_state_events "
                "WHERE plugin_execution_id=:id AND from_state='PENDING' AND to_state='RUNNING'",
                {"id": admitted.plugin_execution_id}),
            _count(engine,
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='PLUGIN_EXECUTION_STARTED' AND target_object_id=:id",
                {"id": admitted.plugin_execution_id}),
        )
        if counts != (1, 1):
            raise AssertionError("RUNNING event and Audit were not atomically persisted once")

        replay = owner.start(StartPluginExecutionCommand(claim, worker))
        if replay.changed or replay.execution_state != "RUNNING":
            raise AssertionError("RUNNING replay did not return changed=false")
        if counts != (
            _count(engine,
                "SELECT count(*) FROM plm.plg_execution_state_events "
                "WHERE plugin_execution_id=:id AND from_state='PENDING' AND to_state='RUNNING'",
                {"id": admitted.plugin_execution_id}),
            _count(engine,
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='PLUGIN_EXECUTION_STARTED' AND target_object_id=:id",
                {"id": admitted.plugin_execution_id}),
        ):
            raise AssertionError("RUNNING replay duplicated event or Audit")

        def rejected_without_write(test_claim, test_worker=worker):
            before = (
                _count(engine, "SELECT count(*) FROM plm.plg_execution_state_events "
                               "WHERE plugin_execution_id=:id", {"id": admitted.plugin_execution_id}),
                _count(engine, "SELECT count(*) FROM plm.aud_events "
                               "WHERE target_object_id=:id AND action='PLUGIN_EXECUTION_STARTED'",
                       {"id": admitted.plugin_execution_id}),
            )
            try:
                owner.start(StartPluginExecutionCommand(test_claim, test_worker))
            except PluginExecutionStartError:
                pass
            else:
                raise AssertionError("invalid claim was not rejected")
            after = (
                _count(engine, "SELECT count(*) FROM plm.plg_execution_state_events "
                               "WHERE plugin_execution_id=:id", {"id": admitted.plugin_execution_id}),
                _count(engine, "SELECT count(*) FROM plm.aud_events "
                               "WHERE target_object_id=:id AND action='PLUGIN_EXECUTION_STARTED'",
                       {"id": admitted.plugin_execution_id}),
            )
            if before != after:
                raise AssertionError("rejected claim caused state/event/Audit writes")

        stale = ClaimedJob(
            job_id=claim.job_id, job_type=claim.job_type, scope=claim.scope,
            project_id=claim.project_id, payload_refs=claim.payload_refs,
            trace_id=claim.trace_id, fencing_token=18, attempt_no=1,
        )
        rejected_without_write(stale)
        rejected_without_write(claim, "wrong.worker")
        bad_binding = ClaimedJob(
            job_id=claim.job_id, job_type=claim.job_type, scope=claim.scope,
            project_id=claim.project_id,
            payload_refs={"output_request_id": str(uuid.uuid4()),
                          "context_snapshot_id": claim.payload_refs["context_snapshot_id"]},
            trace_id=claim.trace_id, fencing_token=19, attempt_no=1,
        )
        rejected_without_write(bad_binding)
        retry = ClaimedJob(
            job_id=claim.job_id, job_type=claim.job_type, scope=claim.scope,
            project_id=claim.project_id, payload_refs=claim.payload_refs,
            trace_id=claim.trace_id, fencing_token=19, attempt_no=2,
        )
        rejected_without_write(retry)

        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('plm.plugin_execution_owner_write','on',true)"))
            conn.execute(text(
                "UPDATE plm.plg_executions SET execution_state='FAILED',"
                "completed_at=statement_timestamp(),error_code='SYNTHETIC_FAILURE',"
                "retryable=false,lock_version=lock_version+1 "
                "WHERE plugin_execution_id=:id"
            ), {"id": admitted.plugin_execution_id})
            conn.execute(text(
                "INSERT INTO plm.plg_execution_state_events "
                "(plugin_execution_id,project_id,from_state,to_state,reason_code,trace_id) "
                "VALUES (:id,:project,'RUNNING','FAILED','SYNTHETIC_FAILURE',:trace)"
            ), {"id": admitted.plugin_execution_id, "project": ids["project"],
                "trace": ids["trace"]})
        rejected_without_write(claim)

        summary = {
            "status": "PASS_SCOPE_LIMITED", "wbs": "PLG-03-A06",
            "runtime": "GitHub Hosted Windows Server 2025 D-drive temporary packaged PG18.6",
            "transition": "PENDING to RUNNING root/start timestamp/lock version, state event, and Audit in one real UoW",
            "audit_failure": "root update and state event rolled back",
            "replay": "changed=false; no duplicate event or Audit",
            "stale_fence_wrong_worker_retry_and_terminal": "rejected with zero event/Audit writes",
            "plugin_process_started": False, "worker_wired": False,
            "customer_data": False, "external_calls": 0,
            "formal_trust": False, "release_eligible": False,
            "parent_archive_sha256": receipt["archive_sha256"],
            "source_commit": os.environ.get("GITHUB_SHA", ""),
            "workflow_run": run_id,
        }
        print("PLG_03_A06_PG18_PASS " + json.dumps(summary, sort_keys=True))
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
