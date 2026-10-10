"""Exercise bundled 0052 migration in disposable PG18 only; never use an existing DB."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from package_windows_unified_candidate import digest_path
from smoke_windows_pg18_sidecar import _start_pg_ctl
from verify_windows_unified_extract import verify


KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
HEAD = "20261001_0052"
PREVIOUS = "20260930_0051"


def _run(arguments: list[str], *, env: dict[str, str] | None = None,
         timeout: int = 240) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, errors="replace",
                            env=env, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"packaged command failed: {Path(arguments[0]).name}; "
                           f"exit={result.returncode}; {result.stdout[-500:]} {result.stderr[-500:]}")
    return result.stdout.strip()


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def smoke(root: Path, candidate: Path, expected_sha256: str) -> dict[str, object]:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    root = root.resolve(strict=True)
    if (root.parent != temp or not root.name.startswith("plm-current-app-stage-") or
            not str(root).isascii() or digest_path(candidate) != expected_sha256):
        raise ValueError("candidate or clean stage identity rejected")
    checked = verify(root, expected_kind=KIND)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(candidate) as archive:
        same_manifest = (root / "manifest.json").read_bytes() == archive.read("manifest.json")
    if (manifest.get("legal_clearance") is not False or
            manifest.get("formal_tls_material_included") is not False or
            not same_manifest):
        raise ValueError("stage source or release boundary differs")
    pg = root / "payload/pgsql/bin"
    python = root / "payload/runtime/python.exe"
    if not (pg / "pg_ctl.exe").is_file() or not python.is_file():
        raise ValueError("bundled runtime missing")
    run = Path(tempfile.mkdtemp(prefix="plm-current-app-db-", dir=temp))
    data, log = run / "data", run / "postgresql.log"
    port = _port()
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(root / "payload/runtime"), str(pg),
                                   str(Path(os.environ["WINDIR"]) / "System32"),
                                   os.environ["WINDIR"]))
    started = False
    try:
        _run([str(pg / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
              "--auth=trust", "--encoding=UTF8", "--locale=C"], timeout=120)
        _start_pg_ctl([str(pg / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                       "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"], log)
        started = True

        def sql(statement: str, database: str = "postgres") -> str:
            return _run([str(pg / "psql.exe"), "-X", "-v", "ON_ERROR_STOP=1",
                         "-h", "127.0.0.1", "-p", str(port), "-U", "poc_admin",
                         "-d", database, "-Atc", statement], env=env)

        def migrate(database: str, revision: str, direction: str = "upgrade") -> None:
            code = ("import sys; from plm_assistant.modules.platform.infrastructure.migration "
                    "import upgrade_database, downgrade_database; "
                    "f=upgrade_database if sys.argv[1]=='upgrade' else downgrade_database; "
                    "f('postgresql+psycopg://poc_admin@127.0.0.1:' + sys.argv[2] + '/' "
                    "+ sys.argv[3], sys.argv[4]); print('PACKAGED_MIGRATION_PASS')")
            result = _run([str(python), "-I", "-B", "-c", code, direction,
                           str(port), database, revision], env=env)
            if "PACKAGED_MIGRATION_PASS" not in result.splitlines():
                raise ValueError("packaged migration marker missing")

        migrate("postgres", PREVIOUS)
        if sql("SELECT version_num FROM plm.alembic_version") != PREVIOUS:
            raise ValueError("predecessor revision mismatch")
        sql("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('poc.current_app')")
        migrate("postgres", HEAD)
        if (sql("SELECT version_num FROM plm.alembic_version") != HEAD or
                sql("SELECT count(*) FROM plm.plt_system_configurations "
                    "WHERE config_key='poc.current_app'") != "1" or
                sql("SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='plm' AND table_name='evd_evidence_records' "
                    "AND column_name='source_parse_record_id'") != "1" or
                sql("SELECT count(*) FROM pg_trigger WHERE tgname='trg_evd_evidence_parse_source'") != "1"):
            raise ValueError("populated upgrade identity/schema mismatch")
        migrate("postgres", PREVIOUS, "downgrade")
        if (sql("SELECT version_num FROM plm.alembic_version") != PREVIOUS or
                sql("SELECT count(*) FROM plm.plt_system_configurations "
                    "WHERE config_key='poc.current_app'") != "1"):
            raise ValueError("safe downgrade lost pre-existing data")
        migrate("postgres", HEAD)
        sql("CREATE DATABASE plm_empty_candidate")
        migrate("plm_empty_candidate", HEAD)
        if sql("SELECT version_num FROM plm.alembic_version", "plm_empty_candidate") != HEAD:
            raise ValueError("fresh empty upgrade head mismatch")
        vector = sql("SELECT extversion FROM pg_extension WHERE extname='vector'")
        _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], env=env,
             timeout=60)
        started = False
        return {"status": "SYNTHETIC_CURRENT_APP_PACKAGED_PG18_MIGRATION_PASS",
                "candidate_sha256": expected_sha256, "payload_file_count": checked["payload_file_count"],
                "head": HEAD, "pgvector_version": vector,
                "populated_data_preserved": True, "empty_database_upgraded": True,
                "safe_downgrade_reupgrade": True, "existing_database_touched": False,
                "release_eligible": False}
    finally:
        if started:
            _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"],
                 env=env, timeout=60)
        status = subprocess.run([str(pg / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            raise RuntimeError(f"synthetic PostgreSQL remains running; data retained at {run}")
        if (run.resolve().parent == temp and run.name.startswith("plm-current-app-db-") and
                run != temp):
            shutil.rmtree(run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.root, args.candidate, args.expected_sha256),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
