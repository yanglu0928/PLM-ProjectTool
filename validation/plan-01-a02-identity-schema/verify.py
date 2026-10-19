"""Disposable Win11/PostgreSQL 18 proof for closed PLN-01 Schema0167."""

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
PREVIOUS = "20261019_0166"


def run(*args: str, detached: bool = False) -> None:
    result = subprocess.run(args, stdout=subprocess.DEVNULL if detached else subprocess.PIPE,
                            stderr=subprocess.DEVNULL if detached else subprocess.PIPE,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def rejects(needle: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert needle in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + needle)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, PREVIOUS)
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    with psycopg.connect(**connection) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Plan Schema Actor','plan schema actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('PLAN01','plan01','Plan test project',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        other = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('PLAN02','plan02','Other plan project',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT count(*) FROM plm.prj_projects WHERE project_id IN (%s,%s)",
                          (project, other)).fetchone()[0] == 2
        rejects("Plan identity Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.pln_plans(project_id,name,created_by) VALUES (%s,'Closed',%s)",
            (project, actor)))
        rejects("Plan identity history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.pln_plans"))
        db.execute("ALTER TABLE plm.pln_plans DISABLE TRIGGER trg_pln_plans__owner")
        try:
            row = db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                "VALUES (%s,'Draft plan',%s) RETURNING plan_id,plan_state,lock_version,"
                "current_approved_version_ref", (project, actor),
            ).fetchone()
            assert row[1:] == ("ACTIVE", 0, None)
            rejects("fk_pln_plans__project", lambda: db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                "VALUES (%s,'Orphan',%s)", (uuid.uuid4(), actor)))
            rejects("fk_pln_plans__creator", lambda: db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                "VALUES (%s,'Orphan actor',%s)", (other, uuid.uuid4())))
            rejects("ck_pln_plans__name", lambda: db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                "VALUES (%s,' padded ',%s)", (other, actor)))
            rejects("ck_pln_plans__state", lambda: db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,plan_state,created_by) "
                "VALUES (%s,'Invalid','APPROVED',%s)", (other, actor)))
            rejects("ck_pln_plans__approved_pointer_closed", lambda: db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,current_approved_version_ref,created_by) "
                "VALUES (%s,'False approval',%s,%s)", (other, uuid.uuid4(), actor)))
            rejects("ck_pln_plans__lock", lambda: db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,lock_version,created_by) "
                "VALUES (%s,'Bad lock',-1,%s)", (other, actor)))
            rejects("Plan identity history prevents downgrade",
                    lambda: command.downgrade(cfg, PREVIOUS))
            assert db.execute("SELECT count(*) FROM plm.pln_plans WHERE plan_id=%s",
                              (row[0],)).fetchone()[0] == 1
            db.execute("DELETE FROM plm.pln_plans WHERE plan_id=%s", (row[0],))
        finally:
            db.execute("ALTER TABLE plm.pln_plans ENABLE TRIGGER trg_pln_plans__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT count(*) FROM plm.prj_projects WHERE project_id IN (%s,%s)",
                          (project, other)).fetchone()[0] == 2
        assert db.execute("SELECT to_regclass('plm.pln_plans')").fetchone()[0] is None
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_01_A02_IDENTITY_SCHEMA_PASS: existing/empty up-down-reup, drift, "
          "closed Owner, FK/check/pointer/history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-plan01-schema-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(PG_SOURCE / name, install / name)
    shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
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
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-plan01-schema-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
