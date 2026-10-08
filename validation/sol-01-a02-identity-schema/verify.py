"""Disposable PostgreSQL 18 proof for Solution identity Schema0136."""

from __future__ import annotations

import runpy
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
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
seed_user = helpers["seed_user"]
PREVIOUS = "20261008_0135"
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
PORT = 0


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True, connect_timeout=5)


def run(*args: str, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(args, stdout=output, stderr=output, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def verify() -> None:
    database = "postgres"
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=PORT, database=database)
    try:
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        with connect(database) as db:
            actor = seed_user(db, "Solution schema actor", "NONE", b"s" * 32)
            project_one = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('SOL001','sol001','Solution one',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
            project_two = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('SOL002','sol002','Solution two',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.prj_projects").fetchone()[0] == 2
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)

        outline_id = uuid.uuid4()
        section_id = uuid.uuid4()
        with connect(database) as db:
            rejects("Solution identity Owner is not installed", lambda: db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Closed',%s)", (outline_id, project_one, actor)))
            rejects("Solution identity history cannot be truncated",
                    lambda: db.execute("TRUNCATE plm.sol_sections CASCADE"))
            db.execute("ALTER TABLE plm.sol_outlines DISABLE TRIGGER trg_sol_outlines__owner")
            db.execute("ALTER TABLE plm.sol_sections DISABLE TRIGGER trg_sol_sections__owner")
            try:
                db.execute(
                    "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Reference-based draft',%s)",
                    (outline_id, project_one, actor))
                assert db.execute(
                    "SELECT current_approved_version_ref FROM plm.sol_outlines "
                    "WHERE solution_outline_id=%s", (outline_id,)).fetchone()[0] is None
                rejects("fk_sol_sections__outline_project", lambda: db.execute(
                    "INSERT INTO plm.sol_sections(project_id,solution_outline_id,section_key,created_by) "
                    "VALUES (%s,%s,'overview',%s)", (project_two, outline_id, actor)))
                db.execute(
                    "INSERT INTO plm.sol_sections(solution_section_id,project_id,solution_outline_id,"
                    "section_key,created_by) VALUES (%s,%s,%s,'overview',%s)",
                    (section_id, project_one, outline_id, actor))
                rejects("uq_sol_sections__outline_key", lambda: db.execute(
                    "INSERT INTO plm.sol_sections(project_id,solution_outline_id,section_key,created_by) "
                    "VALUES (%s,%s,'overview',%s)", (project_one, outline_id, actor)))
                rejects("ck_sol_sections__key", lambda: db.execute(
                    "INSERT INTO plm.sol_sections(project_id,solution_outline_id,section_key,created_by) "
                    "VALUES (%s,%s,' bad ',%s)", (project_one, outline_id, actor)))
                try:
                    command.downgrade(cfg, PREVIOUS)
                except Exception as error:
                    assert "Solution identity history prevents downgrade" in str(error), str(error)
                else:
                    raise AssertionError("Solution history was dropped")
                db.execute("DELETE FROM plm.sol_sections WHERE solution_section_id=%s", (section_id,))
                db.execute("DELETE FROM plm.sol_outlines WHERE solution_outline_id=%s", (outline_id,))
            finally:
                db.execute("ALTER TABLE plm.sol_sections ENABLE TRIGGER trg_sol_sections__owner")
                db.execute("ALTER TABLE plm.sol_outlines ENABLE TRIGGER trg_sol_outlines__owner")
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        print("SOL_01_A02_IDENTITY_SCHEMA_PASS: existing/empty upgrade, downgrade, "
              "drift, closed Owner, project FK, key uniqueness, history guard")
    finally:
        pass


def main() -> None:
    global PORT
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-pg-"))
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
    PORT = free_port()
    started = False
    try:
        run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
            "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start", detached=True)
        started = True
        verify()
    finally:
        if started:
            run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
