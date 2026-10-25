"""Disposable PostgreSQL proof for PlanVersion validation report schema 0189."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]


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
    run_dir = Path(tempfile.mkdtemp(prefix="plm-plan-validation-0189-",
                                    dir=tempfile.gettempdir()))
    if not run_dir.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError("temporary database escaped the system Temp directory")
    data, log, port = run_dir / "data", run_dir / "postgresql.log", free_port()
    started = False
    try:
        run([str(pg_bin / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
             "--auth=trust", "--encoding=UTF8", "--locale=C"])
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
        command.upgrade(cfg, "20261026_0188")
        command.upgrade(cfg, "20261026_0189")
        command.check(cfg)
        dsn = f"host=127.0.0.1 port={port} user=poc_admin dbname=postgres"
        row_id = uuid.uuid4()
        with psycopg.connect(dsn, autocommit=True) as db:
            details = db.execute(
                "SELECT column_name,data_type FROM information_schema.columns "
                "WHERE table_schema='plm' AND table_name='pln_plan_version_validation_results'"
            ).fetchall()
            types = dict(details)
            assert types["blocking_issues"] == "jsonb"
            assert types["warnings"] == "jsonb"
            assert types["coverage_summary"] == "jsonb"
            constraints = db.execute(
                "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='plm' "
                "AND t.relname='pln_plan_version_validation_results' AND c.contype='f'"
            ).fetchone()[0]
            assert constraints == 2
            # Seed a synthetic history row with triggers/FKs disabled only in this
            # disposable superuser-owned cluster to exercise immutable guards and downgrade.
            db.execute("SET session_replication_role=replica")
            db.execute(
                "INSERT INTO plm.pln_plan_version_validation_results "
                "(audit_event_id,plan_version_id,plan_id,project_id,snapshot_fingerprint,valid,"
                "blocking_issues,warnings,coverage_summary,checked_at) "
                "VALUES (%s,%s,%s,%s,%s,false,'[\"TEST_BLOCKED\"]','[]',"
                "'{\"requirement_total\":0,\"requirement_mapped\":0,"
                "\"requirement_excluded\":0,\"requirement_uncovered\":0,"
                "\"solution_total\":0,\"solution_mapped\":0,"
                "\"solution_excluded\":0,\"solution_uncovered\":0}',now())",
                (row_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), b"f" * 32),
            )
            db.execute("RESET session_replication_role")
            rejects(db, "immutable", "UPDATE plm.pln_plan_version_validation_results "
                    "SET valid=true")
            rejects(db, "immutable", "DELETE FROM plm.pln_plan_version_validation_results")
            rejects(db, "cannot be truncated",
                    "TRUNCATE plm.pln_plan_version_validation_results")
        try:
            command.downgrade(cfg, "20261026_0188")
        except RuntimeError as exc:
            assert "history prevents downgrade" in str(exc)
        else:
            raise AssertionError("downgrade must refuse non-empty validation history")
        with psycopg.connect(dsn, autocommit=True) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.pln_plan_version_validation_results "
                "WHERE audit_event_id=%s", (row_id,)).fetchone()[0] == 1
            db.execute("SET session_replication_role=replica")
            db.execute("DELETE FROM plm.pln_plan_version_validation_results WHERE audit_event_id=%s",
                       (row_id,))
            db.execute("RESET session_replication_role")
        command.downgrade(cfg, "20261026_0188")
        with psycopg.connect(dsn, autocommit=True) as db:
            assert db.execute("SELECT to_regclass('plm.pln_plan_version_validation_results')").fetchone()[0] is None
        command.upgrade(cfg, "head")
        command.check(cfg)
        print("PLAN_02_A06_VALIDATION_RESULTS_SCHEMA_PASS: PostgreSQL 18 empty up/down/re-up, "
              "JSONB/FK schema, immutable UPDATE/DELETE/TRUNCATE guards, history-safe downgrade, "
              "Alembic drift clean")
    finally:
        if started:
            run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"],
                timeout=60)
        status = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL still running; data preserved at {run_dir}")
        if (run_dir.name.startswith("plm-plan-validation-0189-")
                and run_dir.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())):
            shutil.rmtree(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-bin", type=Path, required=True)
    verify(parser.parse_args().pg_bin)


if __name__ == "__main__":
    main()
