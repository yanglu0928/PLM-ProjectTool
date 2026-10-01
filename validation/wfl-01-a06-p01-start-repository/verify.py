"""Exercise Workflow start against a disposable loopback PostgreSQL 18 cluster."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.workflow.infrastructure.read_repository import SqlAlchemyWorkflowReadRepository
from plm_assistant.modules.workflow.infrastructure.start_repository import (
    SqlAlchemyWorkflowStartRepository, WorkflowStartRepositoryError,
)


PORT = 55432
PREFIX = "plm-wfl-start-"
SOURCE = Path(__file__).resolve().parents[1] / "wfl-02-a01-p03-history-schema" / "verify.py"
spec = spec_from_file_location("_workflow_history_seed", SOURCE)
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def _command(args: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(args, capture_output=True, text=True, errors="replace",
                            timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} exited {result.returncode}: "
                           f"{(result.stdout + result.stderr)[-1200:]}")
    return result.stdout.strip()


def _own_child(path: Path, root: Path) -> bool:
    resolved = path.resolve(strict=True)
    parent = root.resolve(strict=True)
    return (resolved.parent == parent and resolved != parent and resolved.is_dir()
            and resolved.name.startswith(PREFIX) and not path.is_symlink())


def _matrix() -> None:
    name = "wflstart_" + uuid.uuid4().hex[:12]
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            with fixture.connect(name) as db:
                actor = fixture.insert(db, "auth_users", dict(
                    username_display="Synthetic Workflow Starter",
                    username_normalized="synthetic workflow starter"), "user_id")
                projects = [fixture.insert(db, "prj_projects", dict(
                    project_code=f"WSTART{i}", project_code_normalized=f"wstart{i}",
                    name=f"Synthetic workflow {i}", created_by=actor), "project_id")
                    for i in range(2)]
                with db.transaction():
                    roots = [fixture.initialize(db, project, actor) for project in projects]

            runtime = create_database_runtime(url)
            reader = SqlAlchemyWorkflowReadRepository()
            starter = SqlAlchemyWorkflowStartRepository(reader=reader)

            def current(index: int):
                with runtime.unit_of_work() as tx:
                    return reader.get(tx, projects[index])

            def start(index: int, version: int, *, commit: bool = True):
                with runtime.unit_of_work() as tx:
                    result = starter.start(tx, project_id=projects[index],
                                           expected_version=version)
                    if commit:
                        tx.commit()
                    return result

            def reject(index: int, version: int, code: str):
                with fixture.connect(name) as db:
                    before = db.execute("SELECT workflow_state,current_stage_key,lock_version "
                                        "FROM plm.wfl_project_workflows WHERE project_id=%s",
                                        (projects[index],)).fetchone()
                try:
                    start(index, version)
                except WorkflowStartRepositoryError as error:
                    assert error.code == code, (error.code, code)
                else:
                    raise AssertionError("invalid Workflow start accepted")
                with fixture.connect(name) as db:
                    after = db.execute("SELECT workflow_state,current_stage_key,lock_version "
                                       "FROM plm.wfl_project_workflows WHERE project_id=%s",
                                       (projects[index],)).fetchone()
                    assert after == before

            assert current(0).state == "NOT_STARTED"
            reject(0, 1, "CONFLICT_VERSION")
            with runtime.unit_of_work() as tx:
                try:
                    starter.start(tx, project_id=uuid.uuid4(), expected_version=0)
                except WorkflowStartRepositoryError as error:
                    assert error.code == "RESOURCE_NOT_FOUND"
                else:
                    raise AssertionError("unknown Workflow accepted")
            uncommitted = start(0, 0, commit=False)
            assert uncommitted.state == "ACTIVE" and uncommitted.etag == '"v1"'
            assert current(0).state == "NOT_STARTED", "uncommitted start escaped transaction"

            started = start(0, 0)
            assert (started.workflow_id, started.state, started.current_stage, started.etag) == (
                roots[0], "ACTIVE", "HANDOVER", '"v1"')
            assert tuple(stage.state for stage in started.stages) == (
                "ACTIVE", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED", "NOT_STARTED")
            assert all(item.state == "PENDING" for stage in started.stages for item in stage.checklist_items)
            reject(0, 0, "CONFLICT_VERSION")
            reject(0, 1, "CONFLICT_STATE")

            def competing(_index: int):
                try:
                    return start(1, 0).etag
                except WorkflowStartRepositoryError as error:
                    return error.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(competing, (0, 1)))
            assert sorted(outcomes) == ['"v1"', "CONFLICT_VERSION"], outcomes
            assert current(1).state == "ACTIVE"
            with fixture.connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_records").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_items "
                                  "WHERE item_state='PENDING'").fetchone()[0] == 24
            print("Workflow start repository PASS: real PG18 initial/rollback/commit/version/state/"
                  "two-writer concurrency; no Gate, checklist approval, Audit or public API", flush=True)
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def verify(pg_bin: Path, temp_root: Path) -> None:
    pg_bin, temp_root = pg_bin.resolve(strict=True), temp_root.resolve(strict=True)
    if (not pg_bin.is_dir() or not temp_root.is_dir() or not str(pg_bin).isascii()
            or not str(temp_root).isascii() or not (pg_bin / "initdb.exe").is_file()
            or not (pg_bin / "pg_ctl.exe").is_file()):
        raise ValueError("Existing ASCII PG18 binary and temporary roots required")
    if _command([str(pg_bin / "pg_ctl.exe"), "--version"]) != "pg_ctl (PostgreSQL) 18.6":
        raise ValueError("Expected PostgreSQL 18.6")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", PORT))
        except OSError:
            raise RuntimeError("Existing 55432 listener left untouched") from None

    run = Path(tempfile.mkdtemp(prefix=PREFIX, dir=temp_root))
    if not _own_child(run, temp_root):
        raise RuntimeError("Temporary cluster containment failed; preserving it")
    data, log = run / "data", run / "postgresql.log"
    try:
        _command([str(pg_bin / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
                  "--auth=trust", "--encoding=UTF8", "--locale=C"])
        started = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                                  "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "start"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=60, check=False)
        if started.returncode:
            raise RuntimeError("Disposable PostgreSQL failed to start")
        _matrix()
    finally:
        status = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
                                capture_output=True, timeout=15, check=False)
        if status.returncode == 0:
            try:
                _command([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"])
            except Exception as exc:
                raise RuntimeError(f"Disposable database may still run; preserved at {run}") from exc
        final = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(data), "status"],
                               capture_output=True, timeout=15, check=False)
        if final.returncode == 0 or not _own_child(run, temp_root):
            raise RuntimeError(f"Disposable database or boundary uncertain; preserved at {run}")
        shutil.rmtree(run)
        print("Disposable Workflow PostgreSQL stopped and removed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    options = parser.parse_args()
    verify(options.pg_bin, options.temp_root)
