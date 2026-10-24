"""Disposable Windows PostgreSQL proof for Plan-owned fixed WBS lookup."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.plan.infrastructure.wbs_trace_read_repository import (
    SqlAlchemyPlanWbsTraceReadRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"


def run(*args: str, detached: bool = False) -> None:
    result = subprocess.run(args, stdout=subprocess.DEVNULL if detached else subprocess.PIPE,
                            stderr=subprocess.DEVNULL if detached else subprocess.PIPE,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    with psycopg.connect(**connection) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Trace Read Actor','trace read actor') RETURNING user_id"
        ).fetchone()[0]
        projects = []
        for code in ("TRCWBS1", "TRCWBS2"):
            projects.append(db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES (%s,%s,%s,%s) RETURNING project_id",
                (code, code.casefold(), code, actor)).fetchone()[0])
        tables = (
            ("pln_plans", "trg_pln_plans__owner"),
            ("pln_plan_create_results", "trg_pln_plan_create_results__owner"),
            ("pln_plan_versions", "trg_pln_plan_versions__owner"),
            ("pln_wbs_items", "trg_pln_wbs_items__owner"),
        )
        for table, trigger in tables:
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER {trigger}")
        try:
            plans, versions, items = [], [], []
            for project in projects:
                with db.transaction():
                    plan, created = db.execute(
                        "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                        "VALUES (%s,'Trace Plan',%s) RETURNING plan_id,created_at",
                        (project, actor)).fetchone()
                    db.execute(
                        "INSERT INTO plm.pln_plan_create_results"
                        "(plan_id,project_id,name,created_at) VALUES (%s,%s,'Trace Plan',%s)",
                        (plan, project, created))
                    version = db.execute(
                        "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                        "VALUES (%s,%s,1,%s) RETURNING plan_version_id",
                        (plan, project, actor)).fetchone()[0]
                    item = db.execute(
                        "INSERT INTO plm.pln_wbs_items"
                        "(plan_version_id,plan_id,project_id,wbs_code,name,level,ordinal) "
                        "VALUES (%s,%s,%s,'1','Trace WBS',1,1) RETURNING wbs_item_id",
                        (version, plan, project)).fetchone()[0]
                plans.append(plan)
                versions.append(version)
                items.append(item)
        finally:
            for table, trigger in reversed(tables):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER {trigger}")
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            tx = type("Tx", (), {"session": session})()
            repo = SqlAlchemyPlanWbsTraceReadRepository()
            exact = repo.get_fixed(tx, project_id=projects[0],
                                   wbs_item_id=items[0], plan_version_id=versions[0])
            assert exact is not None
            assert (exact.wbs_item_id, exact.plan_version_id, exact.plan_id,
                    exact.project_id, exact.version_state, exact.plan_state) == (
                        items[0], versions[0], plans[0], projects[0], "DRAFT", "ACTIVE")
            assert repo.get_fixed(tx, project_id=projects[1],
                                  wbs_item_id=items[0], plan_version_id=versions[0]) is None
            assert repo.get_fixed(tx, project_id=projects[0],
                                  wbs_item_id=items[0], plan_version_id=versions[1]) is None
            assert repo.get_fixed(tx, project_id=projects[0],
                                  wbs_item_id=items[1], plan_version_id=versions[0]) is None
    finally:
        engine.dispose()
    print("PLAN_02_A04_P04_A04_P02_A01_WBS_TRACE_READ_PG_PASS: fixed identity, "
          "cross-project/version rejection")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-wbstrace-pg-"))
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
                and scratch.name.startswith("plm-wbstrace-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
