"""Disposable Windows PostgreSQL 18 check for the closed SOL-02 snapshot table."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
PREVIOUS = "20261008_0144"


def run(*args: str, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(args, stdout=output, stderr=output, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    def check_current_head() -> None:
        # Alembic refuses autogenerate checks below the current head. Briefly
        # advance the empty snapshot schema, check drift, then restore A02's
        # closed-write revision for its original negative assertions.
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, "20261009_0145")

    command.upgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('SOL02 Actor','sol02 actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOL02','sol02','Solution outline',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
    command.upgrade(cfg, "20261009_0145")
    check_current_head()
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "20261009_0145")
    check_current_head()

    root = uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rejects("Solution identity Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
            "VALUES (%s,%s,'Closed',%s)", (root, project, actor)))
        rejects("Solution identity Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_outline_create_results(solution_outline_id,project_id,"
            "name,created_at) VALUES (%s,%s,'Closed',now())", (root, project)))
        rejects("Solution identity history cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.sol_outline_create_results"))
        db.execute("ALTER TABLE plm.sol_outlines DISABLE TRIGGER trg_sol_outlines__owner")
        db.execute("ALTER TABLE plm.sol_outline_create_results "
                   "DISABLE TRIGGER trg_sol_outline_create_results__owner")
        try:
            created_at = db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Draft outline',%s) RETURNING created_at",
                (root, project, actor),
            ).fetchone()[0]
            rejects("fk_sol_outline_create_results__outline", lambda: db.execute(
                "INSERT INTO plm.sol_outline_create_results(solution_outline_id,project_id,"
                "name,created_at) VALUES (%s,%s,'Draft outline',%s)",
                (root, uuid.uuid4(), created_at)))
            rejects("ck_sol_outline_create_results__name", lambda: db.execute(
                "INSERT INTO plm.sol_outline_create_results(solution_outline_id,project_id,"
                "name,created_at) VALUES (%s,%s,' bad ',%s)",
                (root, project, created_at)))
            db.execute(
                "INSERT INTO plm.sol_outline_create_results(solution_outline_id,project_id,"
                "name,created_at) VALUES (%s,%s,'Draft outline',%s)",
                (root, project, created_at))
            rejects("pk_sol_outline_create_results", lambda: db.execute(
                "INSERT INTO plm.sol_outline_create_results(solution_outline_id,project_id,"
                "name,created_at) VALUES (%s,%s,'Draft outline',%s)",
                (root, project, created_at)))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "SolutionOutline create result history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("snapshot history was dropped")
            db.execute("DELETE FROM plm.sol_outline_create_results WHERE solution_outline_id=%s", (root,))
            db.execute("DELETE FROM plm.sol_outlines WHERE solution_outline_id=%s", (root,))
        finally:
            db.execute("ALTER TABLE plm.sol_outline_create_results "
                       "ENABLE TRIGGER trg_sol_outline_create_results__owner")
            db.execute("ALTER TABLE plm.sol_outlines ENABLE TRIGGER trg_sol_outlines__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "20261009_0145")
    check_current_head()
    print("SOL_02_A02_OUTLINE_CREATE_RESULT_SCHEMA_PASS: existing/empty upgrade, "
          "downgrade, drift, closed root/result, FK/check/duplicate/history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol02-snapshot-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(PG_SOURCE / name, install / name)
    shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary = install / "bin"
    data = scratch / "data"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    started = False
    try:
        run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
            "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol02-snapshot-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
