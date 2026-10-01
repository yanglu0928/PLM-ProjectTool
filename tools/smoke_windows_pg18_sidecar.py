"""Run a synthetic, loopback-only PostgreSQL/pgvector smoke from a verified sidecar.

No existing cluster is opened. A unique temporary data directory is removed
only after pg_ctl confirms the child server has stopped.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from verify_windows_unified_extract import verify


KIND = "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE"


def check_stage(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if not resolved.is_relative_to(temp_root) or resolved == temp_root:
        raise ValueError("PG sidecar smoke requires an isolated Temp child")
    if not str(resolved).isascii():
        raise ValueError("PG sidecar smoke requires an ASCII path")
    verify(resolved, expected_kind=KIND)
    pg_root = resolved / "payload" / "pgsql"
    for name in ("initdb.exe", "pg_ctl.exe", "psql.exe", "postgres.exe"):
        if not (pg_root / "bin" / name).is_file():
            raise ValueError("PG runtime executable missing")
    return pg_root


def _run(arguments: list[str], *, timeout: int = 90) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, errors="replace",
                            timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"isolated PG command failed: {Path(arguments[0]).name}, exit={result.returncode}, output={result.stdout[-1000:]} {result.stderr[-1000:]}")
    return result.stdout.strip()


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _start_pg_ctl(arguments: list[str], log: Path) -> None:
    # On Windows postgres children can inherit pg_ctl's captured pipe, leaving
    # subprocess.communicate waiting for EOF even after pg_ctl itself exits.
    result = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=60, check=False)
    if result.returncode:
        detail = log.read_text(encoding="utf-8", errors="replace")[-1000:] if log.is_file() else ""
        raise RuntimeError(f"isolated pg_ctl start failed, exit={result.returncode}: {detail}")


def smoke(root: Path) -> dict:
    pg_root = check_stage(root)
    binary = pg_root / "bin"
    port = _free_loopback_port()
    # ASCII prefix/direct Temp child; no customer or previous cluster data.
    run = Path(tempfile.mkdtemp(prefix="plm-pg18-synthetic-", dir=tempfile.gettempdir()))
    try:
        if not str(run).isascii():
            raise ValueError("temporary PG data path is not ASCII")
        data = run / "data"
        log = run / "postgresql.log"
        _run([str(binary / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
              "--auth=trust", "--encoding=UTF8", "--locale=C"], timeout=120)
        started = False
        try:
            _start_pg_ctl([str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                           "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"], log)
            started = True

            def sql(statement: str) -> str:
                return _run([str(binary / "psql.exe"), "-X", "-v", "ON_ERROR_STOP=1",
                             "-h", "127.0.0.1", "-p", str(port), "-U", "poc_admin",
                             "-d", "postgres", "-Atc", statement], timeout=30)

            version = sql("SHOW server_version;")
            sql("CREATE EXTENSION vector;")
            extension = sql("SELECT extversion FROM pg_extension WHERE extname='vector';")
            sql("CREATE TABLE synthetic_vectors (label text PRIMARY KEY, embedding vector(3) NOT NULL);")
            sql("INSERT INTO synthetic_vectors VALUES ('origin','[0,0,0]'),('far','[9,9,9]');")
            sql("CREATE INDEX synthetic_vectors_hnsw_idx ON synthetic_vectors USING hnsw (embedding vector_l2_ops);")
            nearest = sql("SELECT label FROM synthetic_vectors ORDER BY embedding <-> '[0,0,0]'::vector LIMIT 1;")
            method = sql("SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.relname='synthetic_vectors_hnsw_idx';")
            if (version, extension, nearest, method) != ("18.6", "0.8.6", "origin", "hnsw"):
                raise ValueError("isolated PG/vector smoke result mismatch")
        finally:
            if started:
                _run([str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], timeout=60)
        return {"status": "SYNTHETIC_PG18_PGVECTOR_SIDECAR_PASS", "release_eligible": False,
                "postgresql_version": version, "pgvector_version": extension,
                "nearest_label": nearest, "index_method": method,
                "bind_address": "127.0.0.1", "authentication": "trust (ephemeral isolated smoke only)",
                "server_stopped": True, "temporary_data_removed": True}
    finally:
        # A failed start/stop may leave a live child. Never remove its data.
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(run / "data"), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {run}")
        if run.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) and run.name.startswith("plm-pg18-synthetic-"):
            shutil.rmtree(run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
