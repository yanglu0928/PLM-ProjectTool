"""Disposable Windows 11/PostgreSQL check of bounded Requirement scope locks."""

from __future__ import annotations

import runpy
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.requirement.infrastructure.workflow_qualification_repository import (
    SqlAlchemyRequirementWorkflowQualificationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
fixtures = runpy.run_path(str(
    ROOT / "validation" / "req-01-a12-a03-a02-workflow-scope-pg" / "verify.py"
))
connect = fixtures["connect"]
seed_dependencies = fixtures["seed_dependencies"]
insert_scope = fixtures["insert_scope"]
expect_locked = fixtures["expect_locked"]


def main() -> None:
    database = "sol03a06p03a04_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        config = create_migration_config(url)
        command.upgrade(config, "head")
        command.check(config)
        with connect(database) as db:
            ids = seed_dependencies(db)
            scope = insert_scope(db, ids)
            # The historic scope fixture predates acceptance-ref locking.
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for requirement_id in scope["active"]:
                    db.execute(
                        "INSERT INTO plm.req_acceptance_criteria("
                        "requirement_version_id,requirement_id,project_id,ordinal,"
                        "observable_result,verification_method,required_data,"
                        "required_environment,evidence_requirement) VALUES "
                        "(%s,%s,%s,0,'Observable','Check','Dataset',"
                        "'Windows 11','Report')",
                        (scope["versions"][requirement_id], requirement_id,
                         ids["project"]),
                    )
        runtime = create_database_runtime(url)
        with runtime.unit_of_work() as tx:
            original = SqlAlchemyRequirementWorkflowQualificationRepository().lock_complete_scope(
                tx, project_id=ids["project"],
            )
            assert original is not None and original.root_count == 4, "existing scope fixture failed"
        bounded = SqlAlchemyRequirementWorkflowQualificationRepository(
            max_roots=500,
        )
        with runtime.unit_of_work() as tx:
            locked = bounded.lock_complete_scope(tx, project_id=ids["project"])
            assert locked is not None and locked.root_count == 4
            assert len(locked.approved) == 2
            assert tuple(item.snapshot.requirement_id for item in locked.approved) == scope["active"]
            expect_locked(database, "prj_projects", "project_id", ids["project"])

        # The same database scope must fail, never return a truncated three-root set.
        with runtime.unit_of_work() as tx:
            assert SqlAlchemyRequirementWorkflowQualificationRepository(
                max_roots=3,
            ).lock_complete_scope(tx, project_id=ids["project"]) is None
            expect_locked(database, "prj_projects", "project_id", ids["project"])

        empty = uuid.uuid4()
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) VALUES "
                "(%s,'EMPTY-INV','EMPTY-INV','Empty inventory',%s)",
                (empty, ids["actor"]),
            )
        with runtime.unit_of_work() as tx:
            assert bounded.lock_complete_scope(tx, project_id=empty) is None
        command.check(config)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(sql.Identifier(database)))
    print("SOL_03_A06_P03_A04_INVENTORY_PG_PASS: complete bounded scope, "
          "over-cap and empty fail-closed, project lock, schema drift")


def isolated_main() -> None:
    pg_bin = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if (not str(temp_root).isascii() or not str(pg_bin).isascii()
            or not (pg_bin / "initdb.exe").is_file()
            or not (pg_bin / "pg_ctl.exe").is_file()):
        raise RuntimeError("ASCII temporary path and PostgreSQL 18 binaries required")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 55434))
    run = Path(tempfile.mkdtemp(prefix="plm-sol03-inventory-", dir=temp_root))
    if run.parent.resolve() != temp_root or not run.name.startswith("plm-sol03-inventory-"):
        raise RuntimeError("Temporary cluster containment failed")
    data, log = run / "data", run / "postgresql.log"
    try:
        subprocess.run([
            str(pg_bin / "initdb.exe"), f"--pgdata={data}",
            "--username=poc_admin", "--auth=trust", "--encoding=UTF8",
            "--locale=C",
        ], check=True, timeout=120, stdout=subprocess.DEVNULL)
        subprocess.run([
            str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
            "-o", "-h 127.0.0.1 -p 55434", "-w", "start",
        ], check=True, timeout=60, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        main()
    finally:
        status = subprocess.run([
            str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status",
        ], capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            subprocess.run([
                str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-m", "fast",
                "-w", "stop",
            ], check=True, timeout=60, stdout=subprocess.DEVNULL)
        stopped = subprocess.run([
            str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status",
        ], capture_output=True, timeout=15, check=False)
        if stopped.returncode == 0 or run.parent.resolve() != temp_root:
            raise RuntimeError(f"Temporary cluster preserved for inspection: {run}")
        shutil.rmtree(run)


if __name__ == "__main__":
    isolated_main()
