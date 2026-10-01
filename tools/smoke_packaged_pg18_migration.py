"""Apply bundled Alembic revisions to a fresh synthetic PG18 cluster only."""

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

from build_windows_unified_pg18_candidate import KIND
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_pg18_composition import inspect
from plan_windows_unified_pg18_install import CANDIDATE_SHA256
from rehearse_windows_unified_pg18_layout import target_name
from smoke_windows_pg18_sidecar import _start_pg_ctl


HEAD = "20260930_0051"


def verify_layout(root: Path, candidate: Path) -> int:
    inspected_manifest, inspected_hashes = inspect(candidate, CANDIDATE_SHA256, KIND, 21103)
    resolved = root.resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (resolved.parent != temp or not resolved.name.startswith("plm-install-rehearsal-")
            or not str(resolved).isascii()):
        raise ValueError("not a direct ASCII isolated install rehearsal")
    manifest = json.loads((resolved / "app/package-metadata/manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("kind") != KIND or manifest.get("release_eligible") is not False
            or manifest != inspected_manifest or manifest.get("payload_file_count") != 21103):
        raise ValueError("installed layout manifest rejected")
    with zipfile.ZipFile(candidate) as archive:
        for name in ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"):
            if (resolved / "app/package-metadata" / name).read_bytes() != archive.read(name):
                raise ValueError("installed layout metadata differs from pinned ZIP")
    lines = (resolved / "app/package-metadata/payload-sha256sums.txt").read_text(encoding="ascii").splitlines()
    if len(lines) != 21103:
        raise ValueError("installed layout inventory count mismatch")
    seen = set()
    for line in lines:
        digest, separator, source = line.partition("  ")
        target = target_name(source)
        if separator != "  " or len(digest) != 64 or target.casefold() in seen:
            raise ValueError("installed layout hash manifest rejected")
        seen.add(target.casefold())
        if digest_path(resolved / target) != digest:
            raise ValueError("installed layout payload hash mismatch")
    if len(seen) != len(inspected_hashes):
        raise ValueError("installed layout payload inventory differs from ZIP")
    migration = resolved / "runtime/python/packages/plm_assistant/migrations/versions/20260930_0051_platform_maintenance_state.py"
    if not migration.is_file():
        raise ValueError("bundled head migration missing")
    return len(lines)


def _run(arguments: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> str:
    completed = subprocess.run(arguments, capture_output=True, text=True, errors="replace",
                               env=env, timeout=timeout, check=False)
    if completed.returncode:
        raise RuntimeError(f"synthetic packaged migration command failed: {Path(arguments[0]).name}, exit={completed.returncode}, output={completed.stdout[-700:]} {completed.stderr[-700:]}")
    return completed.stdout.strip()


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def smoke(root: Path, candidate: Path) -> dict:
    count = verify_layout(root, candidate)
    root = root.resolve(strict=True)
    pg = root / "runtime/pgsql/bin"
    python = root / "runtime/python/python.exe"
    port = _port()
    run = Path(tempfile.mkdtemp(prefix="plm-package-migration-", dir=tempfile.gettempdir()))
    data = run / "data"
    log = run / "postgresql.log"
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(root / "runtime/python"), str(pg),
                                   str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    started = False
    try:
        _run([str(pg / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
              "--auth=trust", "--encoding=UTF8", "--locale=C"], timeout=120)
        _start_pg_ctl([str(pg / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                       "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"], log)
        started = True
        code = (
            "import sys; from plm_assistant.modules.platform.infrastructure.migration import upgrade_database; "
            "upgrade_database('postgresql+psycopg://poc_admin@127.0.0.1:' + sys.argv[1] + '/postgres'); "
            "print('BUNDLED_MIGRATION_UPGRADE_PASS')"
        )
        migrated = _run([str(python), "-I", "-B", "-c", code, str(port)], env=env, timeout=240)
        if "BUNDLED_MIGRATION_UPGRADE_PASS" not in migrated.splitlines():
            raise ValueError("bundled migration marker missing")

        def sql(statement: str) -> str:
            return _run([str(pg / "psql.exe"), "-X", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1",
                         "-p", str(port), "-U", "poc_admin", "-d", "postgres", "-Atc", statement])

        head = sql("SELECT version_num FROM plm.alembic_version;")
        vector = sql("SELECT extversion FROM pg_extension WHERE extname='vector';")
        table_count = int(sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='plm';"))
        if head != HEAD or vector != "0.8.6" or table_count < 20:
            raise ValueError("bundled schema migration result mismatch")
        _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], timeout=60)
        started = False
        return {"status": "SYNTHETIC_BUNDLED_PG18_MIGRATION_PASS", "release_eligible": False,
                "candidate_sha256": CANDIDATE_SHA256, "payload_file_count": count,
                "alembic_head": head, "pgvector_version": vector, "plm_table_count": table_count,
                "database_source": "fresh ephemeral cluster", "existing_database_touched": False,
                "temporary_server_stopped": True, "temporary_data_removed": True}
    finally:
        if started:
            _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], timeout=60)
        status = subprocess.run([str(pg / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            raise RuntimeError(f"synthetic PostgreSQL remains running; data preserved at {run}")
        if run.resolve().parent == Path(tempfile.gettempdir()).resolve() and run.name.startswith("plm-package-migration-"):
            shutil.rmtree(run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.root, args.candidate), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
