"""Run the PLG-03-A05 admission owner against an isolated hosted PostgreSQL database."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

import psycopg
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend/src"))

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.output.application.job_admission import OutputExecutionAdmission
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.plugin.application.execution_admission import (
    AdmitPluginExecutionCommand,
    PluginExecutionAdmissionError,
    PluginExecutionAdmissionOwner,
)
from plm_assistant.modules.plugin.infrastructure.execution_admission_repository import (
    SqlAlchemyPluginExecutionAdmissionRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from stage_windows_parent_candidate_cloud import safe_name, sha_file, stage_candidate


def _extract_parent_like_smoke(archive: Path, target: Path, expected_archive_sha256: str) -> int:
    """Extract like the already passing parent PG smoke, with full digest checks."""
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if (target.is_symlink() or not target.is_dir() or any(target.iterdir())
            or target.parent.resolve(strict=True) != runner_temp
            or target.drive.upper() == "C:"):
        raise ValueError("A05 direct extraction target is not an owned empty D-drive root")
    if sha_file(archive) != expected_archive_sha256:
        raise ValueError("A05 parent archive changed after staging validation")
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        names = [safe_name(info.filename) for info in infos]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("A05 archive contains duplicate or case-conflicting paths")
        if any((info.external_attr >> 16) & 0o170000 == 0o120000 for info in infos):
            raise ValueError("A05 parent archive symlink rejected")
        manifest_bytes = bundle.read("manifest.json")
        sums = bundle.read("payload-sha256sums.txt")
        manifest = json.loads(manifest_bytes)
        if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
                or manifest.get("release_eligible") is not False
                or manifest.get("legal_clearance") is not False
                or hashlib.sha256(sums).hexdigest()
                != manifest.get("payload_sha256sums_sha256")):
            raise ValueError("A05 parent package manifest or checksum-list identity rejected")
        expected = {}
        for line in sums.decode("ascii").splitlines():
            digest, separator, name = line.partition("  ")
            safe_name(name)
            if (separator != "  " or len(digest) != 64
                    or any(ch not in "0123456789abcdef" for ch in digest)
                    or name in expected):
                raise ValueError("A05 parent checksum list malformed")
            expected[name] = digest
        if (len(expected) != manifest.get("payload_file_count")
                or set(names) != set(expected) | {"manifest.json", "payload-sha256sums.txt"}):
            raise ValueError("A05 parent archive inventory mismatch")
        (target / "manifest.json").write_bytes(manifest_bytes)
        (target / "payload-sha256sums.txt").write_bytes(sums)
        for name, digest in expected.items():
            info = bundle.getinfo(name)
            destination = target.joinpath(*PurePosixPath(name).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            actual = hashlib.sha256()
            with bundle.open(info) as source, destination.open("xb") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
                    actual.update(block)
            if actual.hexdigest() != digest:
                raise ValueError("A05 direct extraction payload hash mismatch")
        return len(expected)


class SyntheticOutputAdmission:
    """Synthetic cross-owner fact for this storage-atomicity test; never formal trust."""

    def __init__(self, facts: dict[uuid.UUID, OutputExecutionAdmission]) -> None:
        self._facts = facts

    def admit_in_transaction(self, transaction: object, claim: ClaimedJob) -> OutputExecutionAdmission:
        if not transaction.session.in_transaction():
            raise RuntimeError("synthetic transaction missing")
        result = self._facts.get(claim.job_id)
        if result is None:
            raise RuntimeError("synthetic output fact missing")
        return result


class FailingAudit:
    def append(self, transaction: object, event: object) -> uuid.UUID:
        raise RuntimeError("synthetic audit failure")


def _checked(args: list[str], timeout: int = 180, *,
             cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, check=False)
    if result.returncode:
        child = Path(args[0]).name.casefold() if args else ""
        if child not in {"initdb.exe", "pg_ctl.exe", "psql.exe"}:
            child = "other"
        detail = (result.stderr or result.stdout)[-2000:] or "no_output"
        raise RuntimeError(
            f"hosted PostgreSQL command failed child={child}; "
            f"exit={result.returncode}; detail={detail}"
        )
    return result.stdout.strip()


def _seed(engine, *, user_id: uuid.UUID, project_id: uuid.UUID,
          job_id: uuid.UUID, context_id: uuid.UUID, request_id: uuid.UUID,
          package_id: uuid.UUID, install_id: uuid.UUID, trace_id: uuid.UUID,
          worker: str, operation: str, seed_plugin: bool) -> None:
    token = 19
    with engine.begin() as conn:
        conn.execute(text(
            "SELECT set_config('plm.plugin_installation_owner_write','on',true)"
        ))
        conn.execute(text(
            "INSERT INTO plm.auth_users (user_id,username_display,username_normalized) "
            "VALUES (:id,'Hosted synthetic admission','hosted_admission_' || :suffix)"
        ), {"id": user_id, "suffix": user_id.hex[:12]})
        conn.execute(text(
            "INSERT INTO plm.prj_projects "
            "(project_id,project_code,project_code_normalized,name,created_by) "
            "VALUES (:id,:code,:code,'Hosted synthetic PLG03 project',:user)"
        ), {"id": project_id, "code": "A05-" + project_id.hex[:12], "user": user_id})
        conn.execute(text(
            "INSERT INTO plm.out_context_snapshots "
            "(context_snapshot_id,project_id,source_version_refs,context_payload,"
            "context_fingerprint,created_by) "
            "VALUES (:id,:project,'[{\"synthetic\":true}]'::jsonb,'{}'::jsonb,"
            "decode(repeat('2a',32),'hex'),:user)"
        ), {"id": context_id, "project": project_id, "user": user_id})
        conn.execute(text(
            "INSERT INTO plm.job_jobs "
            "(job_id,owner_module,job_type,scope,project_id,actor_ref,trace_id,"
            "payload_refs,idempotency_key,state,attempt_count,max_attempts,fencing_token,"
            "lease_expires_at) "
            "VALUES (:id,'output','OUTPUT_GENERATE','PROJECT',:project,:user,:trace,"
            "'{}'::jsonb,:key,'RUNNING',1,3,:token,"
            "statement_timestamp()+interval '10 minutes')"
        ), {"id": job_id, "project": project_id, "user": user_id, "trace": str(trace_id),
            "key": "plg03-a05-" + job_id.hex, "token": token})
        conn.execute(text(
            "INSERT INTO plm.job_leases "
            "(job_id,worker_ref,fencing_token,state,lease_expires_at) "
            "VALUES (:job,:worker,:token,'ACTIVE',statement_timestamp()+interval '10 minutes')"
        ), {"job": job_id, "worker": worker, "token": token})
        conn.execute(text(
            "INSERT INTO plm.job_attempts (job_id,attempt_no,worker_ref,fencing_token) "
            "VALUES (:job,1,:worker,:token)"
        ), {"job": job_id, "worker": worker, "token": token})
        conn.execute(text(
            "INSERT INTO plm.out_output_requests "
            "(output_request_id,project_id,output_type,template_version_ref,"
            "source_version_refs,output_policy_ref,plugin_operation,context_snapshot_id,"
            "input_fingerprint,request_state,job_ref,idempotency_key,trace_id,requested_by) "
            "VALUES (:id,:project,'DOCX',:template,'[\"synthetic-source\"]'::jsonb,"
            "'synthetic.policy.v1',:operation,:context,decode(repeat('3b',32),'hex'),"
            "'QUEUED',:job,:key,:trace,:user)"
        ), {"id": request_id, "project": project_id, "template": uuid.uuid4(),
            "operation": operation, "context": context_id, "job": job_id,
            "key": "plg03-a05-output-" + job_id.hex, "trace": trace_id, "user": user_id})
        if seed_plugin:
            conn.execute(text(
                "INSERT INTO plm.plg_packages "
                "(plugin_package_id,plugin_id_normalized,plugin_version,package_sha256,"
                "manifest_snapshot,signature,signer_key_ref,compatibility_policy_ref,"
                "package_state,verified_at) "
                "VALUES (:id,'synthetic.admission','1.0.0',decode(repeat('4c',32),'hex'),"
                "'{\"schema_version\":1}'::jsonb,decode('01','hex'),'synthetic-only',"
                "'synthetic.compat.v1','VERIFIED',statement_timestamp())"
            ), {"id": package_id})
            conn.execute(text(
                "INSERT INTO plm.plg_manifest_operations "
                "(plugin_package_id,operation_id,output_types,plugin_api_version) "
                "VALUES (:package,:operation,'[\"DOCX\"]'::jsonb,'1')"
            ), {"package": package_id, "operation": operation})
            conn.execute(text(
                "INSERT INTO plm.plg_installations "
                "(plugin_installation_id,plugin_package_id,plugin_id_normalized,"
                "installation_state,validated_runtime_snapshot,installed_by,enabled_by,"
                "enabled_at,created_by,updated_by) "
                "VALUES (:id,:package,'synthetic.admission','ENABLED','{}'::jsonb,"
                ":user,:user,statement_timestamp(),:user,:user)"
            ), {"id": install_id, "package": package_id, "user": user_id})
            conn.execute(text(
                "INSERT INTO plm.plg_enabled_operations "
                "(plugin_installation_id,operation_id,plugin_package_id,plugin_id_normalized) "
                "VALUES (:install,:operation,:package,'synthetic.admission')"
            ), {"install": install_id, "operation": operation, "package": package_id})


def _admission(*, job_id: uuid.UUID, project_id: uuid.UUID,
               request_id: uuid.UUID, context_id: uuid.UUID,
               operation: str) -> OutputExecutionAdmission:
    return OutputExecutionAdmission(
        output_request_id=request_id, project_id=project_id, job_id=job_id,
        context_snapshot_id=context_id, output_type="DOCX",
        template_version_ref=uuid.uuid4(), source_version_refs=(uuid.uuid4(),),
        output_policy_ref="synthetic.policy.v1", plugin_operation=operation,
        input_fingerprint=bytes.fromhex("3b" * 32),
        context_fingerprint=bytes.fromhex("2a" * 32),
    )


def _count(engine, sql: str, values: dict | None = None) -> int:
    with engine.connect() as conn:
        return conn.execute(text(sql), values or {}).scalar_one()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--verification-summary", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()
    runner_temp = Path(os.environ.get("RUNNER_TEMP", "")).resolve(strict=True)
    root = args.run_root
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if (sys.platform != "win32" or runner_temp.drive.upper() != "D:"
            or root.parent.resolve(strict=True) != runner_temp
            or root.drive.upper() == "C:" or root.exists() or root.is_symlink()
            or not run_id.isascii() or not run_id.isdigit()):
        raise ValueError("A05 requires an owned new D-drive hosted Windows temp root")
    root.mkdir()
    stage = runner_temp / ("plg03-a05-stage-" + run_id)
    port_sock = socket.socket()
    port_sock.bind(("127.0.0.1", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()
    data_dir = root / "pgdata"
    pg_log = root / "postgres.log"
    staged = False
    started = False
    created_database = False
    engine = None
    database = "plm_plg03a05_" + run_id[-10:]
    summary = {}
    try:
        receipt = stage_candidate(args.archive, args.verification_summary, stage)
        staged = True
        if (receipt.get("status") != "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED"
                or receipt.get("installation_performed") is not False
                or receipt.get("services_started") is not False):
            raise ValueError("A05 parent staging receipt rejected")
        if stage.parent.resolve(strict=True) != runner_temp or stage.drive.upper() == "C:":
            raise ValueError("A05 staging root escaped its D-drive runner temp")
        shutil.rmtree(stage)
        staged = False
        _extract_parent_like_smoke(args.archive, root, receipt["archive_sha256"])
        pg_root = root / "payload" / "pgsql"
        pg_bin = pg_root / "bin"
        initdb, pg_ctl = (pg_bin / name for name in ("initdb.exe", "pg_ctl.exe"))
        if (not pg_bin.is_dir()
                or any(p.is_symlink() or not p.is_file() for p in (initdb, pg_ctl))):
            raise ValueError("verified parent package PostgreSQL runtime missing")
        _checked([str(initdb), "-D", str(data_dir), "-U", "postgres",
                  "--auth-local=trust", "--auth-host=trust", "--no-locale", "-E", "UTF8"])
        start = subprocess.run(
            [str(pg_ctl), "-D", str(data_dir), "-l", str(pg_log),
             "-o", f"-h 127.0.0.1 -p {port} -c listen_addresses=127.0.0.1",
             "-w", "start"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, check=False,
        )
        if start.returncode:
            raise RuntimeError("temporary packaged PG18 failed to start: " +
                               (start.stderr or start.stdout)[-2000:])
        started = True
        admin_url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{database}"')
        created_database = True
        url = URL.create("postgresql+psycopg", username="postgres", host="127.0.0.1",
                         port=port, database=database)
        with psycopg.connect(f"postgresql://postgres@127.0.0.1:{port}/{database}",
                             autocommit=True) as conn:
            conn.execute("CREATE EXTENSION vector")
        upgrade_database(url)
        engine = create_engine(url)
        session_factory = sessionmaker(engine, expire_on_commit=False)
        make_uow = lambda: SqlAlchemyUnitOfWork(session_factory)
        jobs = JobLeaseService(
            unit_of_work=make_uow, repository=SqlAlchemyJobLeaseRepository(),
        )
        plugin_repo = SqlAlchemyPluginExecutionAdmissionRepository()
        operation = "synthetic.admission.generate"
        worker = "synthetic.worker"
        cases = []
        shared_package_id, shared_install_id = uuid.uuid4(), uuid.uuid4()
        for suffix in ("success", "rollback"):
            ids = {key: uuid.uuid4() for key in
                   ("user", "project", "job", "context", "request", "trace")}
            ids["package"] = shared_package_id
            ids["install"] = shared_install_id
            _seed(engine, user_id=ids["user"], project_id=ids["project"],
                  job_id=ids["job"], context_id=ids["context"],
                  request_id=ids["request"], package_id=ids["package"],
                  install_id=ids["install"], trace_id=ids["trace"],
                  worker=worker, operation=operation, seed_plugin=(suffix == "success"))
            claim = ClaimedJob(
                job_id=ids["job"], job_type="OUTPUT_GENERATE", scope="PROJECT",
                project_id=ids["project"], payload_refs={}, trace_id=str(ids["trace"]),
                fencing_token=19, attempt_no=1,
            )
            fact = _admission(job_id=ids["job"], project_id=ids["project"],
                              request_id=ids["request"], context_id=ids["context"],
                              operation=operation)
            cases.append((ids, claim, fact))
        outputs = SyntheticOutputAdmission({claim.job_id: fact for _, claim, fact in cases})
        owner = PluginExecutionAdmissionOwner(
            unit_of_work=make_uow, jobs=jobs, output_admission=outputs,
            targets=plugin_repo, repository=plugin_repo,
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        first_ids, first_claim, _ = cases[0]
        command = AdmitPluginExecutionCommand(first_claim, worker)
        admitted = owner.admit(command)
        if not admitted.created or admitted.execution_state != "PENDING":
            raise AssertionError("first admission did not create PENDING execution")
        root_count = _count(engine, "SELECT count(*) FROM plm.plg_executions WHERE job_id=:job",
                            {"job": first_claim.job_id})
        event_count = _count(engine,
            "SELECT count(*) FROM plm.plg_execution_state_events WHERE plugin_execution_id=:id",
            {"id": admitted.plugin_execution_id})
        audit_count = _count(engine,
            "SELECT count(*) FROM plm.aud_events WHERE action='PLUGIN_EXECUTION_ADMIT' "
            "AND target_object_id=:id", {"id": admitted.plugin_execution_id})
        if (root_count, event_count, audit_count) != (1, 1, 1):
            raise AssertionError("PENDING root/state event/Audit were not atomically persisted")
        replay = owner.admit(command)
        if replay.created or replay.plugin_execution_id != admitted.plugin_execution_id:
            raise AssertionError("exact same-job replay was not idempotent")
        if (_count(engine, "SELECT count(*) FROM plm.plg_execution_state_events "
                           "WHERE plugin_execution_id=:id", {"id": admitted.plugin_execution_id}) != 1
                or _count(engine, "SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='PLUGIN_EXECUTION_ADMIT' AND target_object_id=:id",
                          {"id": admitted.plugin_execution_id}) != 1):
            raise AssertionError("replay duplicated immutable event or audit")

        stale = ClaimedJob(
            job_id=first_claim.job_id, job_type=first_claim.job_type, scope=first_claim.scope,
            project_id=first_claim.project_id, payload_refs=first_claim.payload_refs,
            trace_id=first_claim.trace_id, fencing_token=18, attempt_no=1,
        )
        rejected = False
        try:
            owner.admit(AdmitPluginExecutionCommand(stale, worker))
        except PluginExecutionAdmissionError:
            rejected = True
        if not rejected or _count(engine, "SELECT count(*) FROM plm.plg_executions") != 1:
            raise AssertionError("stale fencing claim was not rejected without writes")

        retry = ClaimedJob(
            job_id=first_claim.job_id, job_type=first_claim.job_type, scope=first_claim.scope,
            project_id=first_claim.project_id, payload_refs=first_claim.payload_refs,
            trace_id=first_claim.trace_id, fencing_token=19, attempt_no=2,
        )
        rejected = False
        try:
            owner.admit(AdmitPluginExecutionCommand(retry, worker))
        except PluginExecutionAdmissionError:
            rejected = True
        if not rejected or _count(engine, "SELECT count(*) FROM plm.plg_executions") != 1:
            raise AssertionError("attempt >1 was not rejected before persistence")

        second_ids, second_claim, _ = cases[1]
        failing_owner = PluginExecutionAdmissionOwner(
            unit_of_work=make_uow, jobs=jobs, output_admission=outputs,
            targets=plugin_repo, repository=plugin_repo, audit=FailingAudit(),
        )
        before_audits = _count(engine,
            "SELECT count(*) FROM plm.aud_events WHERE action='PLUGIN_EXECUTION_ADMIT'")
        rejected = False
        try:
            failing_owner.admit(AdmitPluginExecutionCommand(second_claim, worker))
        except PluginExecutionAdmissionError:
            rejected = True
        if not rejected:
            raise AssertionError("synthetic audit failure was not returned as fail-closed")
        if (_count(engine, "SELECT count(*) FROM plm.plg_executions WHERE job_id=:job",
                   {"job": second_claim.job_id}) != 0
                or _count(engine, "SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='PLUGIN_EXECUTION_ADMIT'") != before_audits):
            raise AssertionError("audit failure did not roll back execution atomically")

        guard_closed = False
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO plm.plg_executions "
                    "(plugin_execution_id,project_id,output_request_id,"
                    "output_context_snapshot_id,plugin_installation_id,plugin_package_id,"
                    "plugin_id_normalized,operation_id,context_fingerprint,job_id,attempt_no,"
                    "idempotency_key,trace_id) VALUES "
                    "(:execution,:project,:request,:context,:install,:package,"
                    "'synthetic.admission',:operation,decode(repeat('2a',32),'hex'),"
                    ":job,1,:key,:trace)"
                ), {"execution": uuid.uuid4(), "project": second_ids["project"],
                    "request": second_ids["request"], "context": second_ids["context"],
                    "install": second_ids["install"], "package": second_ids["package"],
                    "operation": operation, "job": second_ids["job"],
                    "key": "guard-" + uuid.uuid4().hex, "trace": second_ids["trace"]})
        except Exception as exc:
            guard_closed = "owner controlled" in str(exc).casefold()
            if not guard_closed:
                raise
        if not guard_closed:
            raise AssertionError("PluginExecution DB owner-write guard was not closed")

        summary = {
            "status": "PASS_SCOPE_LIMITED",
            "wbs": "PLG-03-A05",
            "runtime": "GitHub hosted Windows Server 2025 D-drive temporary PG18",
            "postgresql_version": "18.6",
            "first_admission": "PENDING root/state event/Audit in one real SQLAlchemy transaction",
            "replay": "idempotent; event and Audit counts unchanged",
            "stale_fencing": "rejected with zero additional writes",
            "retry_attempt": "attempt 2 rejected with zero additional writes",
            "audit_failure": "root/event/Audit transaction rolled back",
            "owner_guard": "direct unauthorised root write rejected",
            "output_admission": "synthetic port only; formal publisher trust not asserted",
            "plugin_process_started": False,
            "customer_data": False,
            "release_eligible": False,
            "parent_archive_sha256": receipt["archive_sha256"],
            "source_commit": os.environ.get("GITHUB_SHA", ""),
            "workflow_run": run_id,
        }
        print("PLG_03_A05_PG18_PASS " + json.dumps(summary, sort_keys=True))
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
        if started:
            pg_ctl = stage / "payload" / "pgsql" / "bin" / "pg_ctl.exe"
            stop = subprocess.run(
                [str(pg_ctl), "-D", str(data_dir), "-m", "fast", "-w", "stop"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180, check=False,
            )
            if stop.returncode:
                raise RuntimeError("temporary PostgreSQL shutdown was not confirmed")
        for owned in (stage, root):
            if owned.exists():
                resolved = owned.resolve(strict=True)
                if (resolved.parent != runner_temp or owned.is_symlink()
                        or resolved.drive.upper() == "C:"):
                    raise RuntimeError("refusing to clean outside owned D-drive runner temp")
                shutil.rmtree(owned)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n",
                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
