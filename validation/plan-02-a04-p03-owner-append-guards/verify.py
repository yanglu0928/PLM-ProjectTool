"""Disposable PostgreSQL proof for Plan append-only guard migration 0188."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
PREVIOUS = "20261026_0187"
GUARDS = (
    "guard_plan_version_foundation",
    "guard_wbs_item_foundation",
    "guard_wbs_dependency_foundation",
    "guard_plan_milestone_foundation",
    "guard_wbs_requirement_ref_foundation",
    "guard_wbs_solution_ref_foundation",
    "guard_wbs_evidence_ref_foundation",
    "guard_plan_snapshot_child_foundation",
)


def run(args: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(args, capture_output=True, text=True, errors="replace",
                            timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed ({result.returncode}): "
                           f"{result.stdout[-1000:]} {result.stderr[-1000:]}")
    return result.stdout.strip()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def rejects(db: psycopg.Connection, needle: str, sql: str) -> None:
    try:
        db.execute(sql)
    except Exception as exc:
        db.rollback()
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r}, got {exc!r}") from exc
    else:
        raise AssertionError(f"expected database rejection containing {needle!r}")


def verify(pg_bin: Path) -> None:
    pg_bin = pg_bin.resolve(strict=True)
    for executable in ("initdb.exe", "pg_ctl.exe"):
        if not (pg_bin / executable).is_file():
            raise ValueError(f"missing PostgreSQL executable: {executable}")
    run_dir = Path(tempfile.mkdtemp(prefix="plm-plan-0188-", dir=tempfile.gettempdir()))
    if not run_dir.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError("temporary database escaped the system Temp directory")
    data = run_dir / "data"
    log = run_dir / "postgresql.log"
    port = free_port()
    started = False
    try:
        run([str(pg_bin / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
             "--auth=trust", "--encoding=UTF8", "--locale=C"])
        # PostgreSQL's child inherits handles on Windows; detach pg_ctl output so
        # subprocess does not wait for the server process to close captured pipes.
        started_result = subprocess.run(
            [str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
             "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60, check=False)
        if started_result.returncode:
            raise RuntimeError(f"isolated PostgreSQL failed to start; see {log}")
        started = True
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=port, database="postgres")
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        dsn = f"host=127.0.0.1 port={port} user=poc_admin dbname=postgres"

        # Exercise every revised guard using real PostgreSQL trigger invocation.
        with psycopg.connect(dsn, autocommit=True) as db:
            attached = dict(db.execute(
                "SELECT p.proname, count(*) FROM pg_trigger t "
                "JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='plm' AND NOT t.tgisinternal "
                "GROUP BY p.proname").fetchall())
            for function in GUARDS:
                assert attached.get(function, 0) > 0, f"no table trigger attached to {function}"
            assert attached.get("reject_plan_snapshot_child_truncate", 0) > 0
            db.execute("CREATE TABLE public.guard_probe (id integer)")
            for index, function in enumerate(GUARDS):
                db.execute("TRUNCATE public.guard_probe")
                db.execute(f"CREATE TRIGGER probe BEFORE INSERT OR UPDATE OR DELETE "
                           f"ON public.guard_probe FOR EACH ROW EXECUTE FUNCTION plm.{function}()")
                db.execute("INSERT INTO public.guard_probe VALUES (1)")
                rejects(db, "snapshots are immutable", "UPDATE public.guard_probe SET id=2")
                rejects(db, "snapshots are immutable", "DELETE FROM public.guard_probe")
                db.execute("DROP TRIGGER probe ON public.guard_probe")
            db.execute("CREATE TRIGGER probe BEFORE INSERT OR UPDATE OR DELETE ON public.guard_probe "
                       "FOR EACH ROW EXECUTE FUNCTION plm.guard_plan_version_foundation()")
            db.execute("CREATE TRIGGER no_truncate BEFORE TRUNCATE ON public.guard_probe "
                       "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plan_snapshot_child_truncate()")
            rejects(db, "cannot be truncated", "TRUNCATE public.guard_probe")
            db.execute("INSERT INTO public.guard_probe VALUES (7)")

        command.downgrade(cfg, PREVIOUS)
        with psycopg.connect(dsn, autocommit=True) as db:
            assert db.execute("SELECT count(*) FROM public.guard_probe WHERE id=7").fetchone()[0] == 1
            rejects(db, "Owner is not installed", "INSERT INTO public.guard_probe VALUES (8)")
        command.upgrade(cfg, "head")
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("INSERT INTO public.guard_probe VALUES (9)")
            assert db.execute("SELECT count(*) FROM public.guard_probe").fetchone()[0] == 3
            db.execute("DROP TABLE public.guard_probe")
        command.check(cfg)
        print("PLAN_02_A04_P03_OWNER_APPEND_GUARDS_PASS: PostgreSQL 18 migration up/down/re-up, "
              "8 guards permit INSERT and reject UPDATE/DELETE, TRUNCATE remains blocked, "
              "downgrade preserves rows and restores closed guards, drift clean")
    finally:
        if started:
            run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"],
                timeout=60)
        status = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL still running; data preserved at {run_dir}")
        # This path was just created by this script and confirmed below the system Temp root.
        if run_dir.name.startswith("plm-plan-0188-") and run_dir.resolve().is_relative_to(
                Path(tempfile.gettempdir()).resolve()):
            shutil.rmtree(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-bin", type=Path, required=True)
    verify(parser.parse_args().pg_bin)


if __name__ == "__main__":
    main()
