"""Run the REQ-03 owner proof on a fresh disposable PG18.6 cluster."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


PORT = 55434
PREFIX = "plm-trc01a03p01-"
PG_BIN = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")


def command(args, timeout=120):
    result = subprocess.run(args, capture_output=True, text=True,
                            errors="replace", timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed: {(result.stdout + result.stderr)[-2000:]}")
    return result.stdout.strip()


def main():
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", PORT))
        except OSError as exc:
            raise RuntimeError("Port 55434 is occupied; existing instance untouched") from exc
    if command([str(PG_BIN / "pg_ctl.exe"), "--version"]) != "pg_ctl (PostgreSQL) 18.6":
        raise RuntimeError("Expected PostgreSQL 18.6")
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if not str(temp_root).isascii():
        raise RuntimeError("PostgreSQL temporary root must be ASCII")
    run = Path(tempfile.mkdtemp(prefix=PREFIX, dir=temp_root))
    data, log = run / "data", run / "postgresql.log"
    try:
        command([str(PG_BIN / "initdb.exe"), f"--pgdata={data}",
                 "--username=poc_admin", "--auth=trust", "--encoding=UTF8",
                 "--locale=C"])
        started = subprocess.run(
            [str(PG_BIN / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
             "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60, check=False,
        )
        if started.returncode:
            raise RuntimeError("Isolated PostgreSQL failed to start")
        print(command([sys.executable, str(Path(__file__).with_name("verify.py"))],
                      timeout=900))
    finally:
        status = subprocess.run([str(PG_BIN / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            command([str(PG_BIN / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"])
        final = subprocess.run([str(PG_BIN / "pg_ctl.exe"), "-D", str(data), "status"],
                               capture_output=True, timeout=15, check=False)
        if final.returncode == 0:
            raise RuntimeError(f"PG remains active; data preserved at {run}")
        if (run.resolve(strict=True).parent != temp_root or
                not run.name.startswith(PREFIX)):
            raise RuntimeError(f"Temporary containment changed; preserved {run}")
        shutil.rmtree(run)
        print("Temporary PostgreSQL cluster stopped and removed")


if __name__ == "__main__":
    main()
