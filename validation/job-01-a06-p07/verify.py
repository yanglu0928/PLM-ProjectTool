"""Run existing Jobs HTTP/PG matrices on one disposable loopback PG18 instance.

The historical fixtures use port 55432. This runner refuses an occupied port,
creates only a fresh cluster below an explicitly supplied ASCII temp root, and
does not touch any existing database or production credential.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


PORT = 55432
PREFIX = "plm-job-read-matrix-"
MATRICES = (
    ("validation/job-01-a05-p05-windows/verify.py", "Windows Job list PASS:"),
    ("validation/job-01-a04-p04-windows/verify.py", "Document Windows factories PASS:"),
)


def _command(args: list[str], *, timeout: int = 90) -> str:
    result = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} exited {result.returncode}: {(result.stdout + result.stderr)[-1800:]}")
    return result.stdout.strip()


def _port_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", PORT))
        except OSError:
            return False
        return True


def _safe_run_dir(run: Path, temp_root: Path) -> bool:
    """Allow removal only of our exact new direct child of the named temp root."""
    root = temp_root.resolve(strict=True)
    target = run.resolve(strict=True)
    return target.parent == root and target.name.startswith(PREFIX) and target != root and target.is_dir()


def verify(*, repo: Path, pg_bin: Path, python: Path, temp_root: Path) -> None:
    repo = repo.resolve(strict=True)
    pg_bin = pg_bin.resolve(strict=True)
    python = python.resolve(strict=True)
    temp_root = temp_root.resolve(strict=True)
    if not temp_root.is_dir() or not str(temp_root).isascii() or not str(pg_bin).isascii():
        raise ValueError("ASCII existing PG binary and temporary roots required")
    if not (pg_bin / "initdb.exe").is_file() or not (pg_bin / "pg_ctl.exe").is_file() or not python.is_file():
        raise ValueError("PG18 and Python executables required")
    if any(not (repo / relative).is_file() for relative, _ in MATRICES):
        raise ValueError("Jobs validation matrix missing")
    if _command([str(pg_bin / "pg_ctl.exe"), "--version"]) != "pg_ctl (PostgreSQL) 18.6":
        raise ValueError("Expected PostgreSQL 18.6 runtime")
    if not _port_free():
        raise RuntimeError(f"Loopback port {PORT} is already occupied; existing instance untouched")

    run = Path(tempfile.mkdtemp(prefix=PREFIX, dir=temp_root))
    if not _safe_run_dir(run, temp_root) or not str(run).isascii():
        raise RuntimeError("Fresh temporary path failed containment check; preserving it")
    data, log = run / "data", run / "postgresql.log"
    try:
        _command([str(pg_bin / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
                  "--auth=trust", "--encoding=UTF8", "--locale=C"], timeout=120)
        started = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                                  "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=60, check=False)
        if started.returncode:
            details = log.read_text(encoding="utf-8", errors="replace")[-1200:] if log.is_file() else ""
            raise RuntimeError(f"Isolated PG start failed: {details}")
        for relative, marker in MATRICES:
            result = _command([str(python), str(repo / relative)], timeout=900)
            if marker not in result:
                raise RuntimeError(f"{relative} exited without its completion marker")
            print(f"{relative}: {marker}", flush=True)
    finally:
        status = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            try:
                _command([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], timeout=60)
            except Exception as exc:
                raise RuntimeError(f"Isolated PG may remain active; data preserved at {run}") from exc
        final = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
                               capture_output=True, timeout=15, check=False)
        if final.returncode == 0:
            raise RuntimeError(f"Isolated PG remains active; data preserved at {run}")
        if not _safe_run_dir(run, temp_root):
            raise RuntimeError(f"Temporary data containment changed; data preserved at {run}")
        shutil.rmtree(run)
        print("Isolated PG stopped; temporary cluster removed", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    verify(repo=args.repo, pg_bin=args.pg_bin, python=args.python, temp_root=args.temp_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
