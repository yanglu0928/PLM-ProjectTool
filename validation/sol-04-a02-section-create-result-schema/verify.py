"""Win11 disposable PG18 proof for closed SOL_SECTION_CREATE first result."""

from __future__ import annotations

import importlib.util
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
SPEC = importlib.util.spec_from_file_location(
    "outline_result_schema", ROOT / "validation/sol-02-a02-outline-create-result-schema/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
PREVIOUS = "20261009_0146"
CURRENT = "20261009_0147"


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('SOL04 Actor','sol04 actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOL04','sol04','Section project',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
        outline = uuid.uuid4()
        with db.transaction():
            created_at = db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Parent outline',%s) RETURNING created_at",
                (outline, project, actor)).fetchone()[0]
            db.execute("INSERT INTO plm.sol_outline_create_results"
                       "(solution_outline_id,project_id,name,created_at) "
                       "VALUES (%s,%s,'Parent outline',%s)",
                       (outline, project, created_at))
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)

    section = uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        prior.rejects("Solution identity operation is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
            "project_id,section_key,created_by) VALUES (%s,%s,%s,'C1',%s)",
            (section, outline, project, actor)))
        prior.rejects("Solution identity operation is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_section_create_results(solution_section_id,"
            "solution_outline_id,project_id,section_key,created_at) "
            "VALUES (%s,%s,%s,'C1',now())", (section, outline, project)))
        prior.rejects("Solution identity history cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.sol_section_create_results"))
        db.execute("ALTER TABLE plm.sol_sections DISABLE TRIGGER trg_sol_sections__owner")
        db.execute("ALTER TABLE plm.sol_section_create_results "
                   "DISABLE TRIGGER trg_sol_section_create_results__owner")
        try:
            created_at = db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'C1',%s) "
                "RETURNING created_at", (section, outline, project, actor)).fetchone()[0]
            prior.rejects("fk_sol_section_create_results__section", lambda: db.execute(
                "INSERT INTO plm.sol_section_create_results(solution_section_id,"
                "solution_outline_id,project_id,section_key,created_at) "
                "VALUES (%s,%s,%s,'C1',%s)",
                (section, uuid.uuid4(), project, created_at)))
            prior.rejects("ck_sol_section_create_results__key", lambda: db.execute(
                "INSERT INTO plm.sol_section_create_results(solution_section_id,"
                "solution_outline_id,project_id,section_key,created_at) "
                "VALUES (%s,%s,%s,' bad ',%s)",
                (section, outline, project, created_at)))
            db.execute("INSERT INTO plm.sol_section_create_results(solution_section_id,"
                       "solution_outline_id,project_id,section_key,created_at) "
                       "VALUES (%s,%s,%s,'C1',%s)",
                       (section, outline, project, created_at))
            prior.rejects("pk_sol_section_create_results", lambda: db.execute(
                "INSERT INTO plm.sol_section_create_results(solution_section_id,"
                "solution_outline_id,project_id,section_key,created_at) "
                "VALUES (%s,%s,%s,'C1',%s)",
                (section, outline, project, created_at)))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "SolutionSection create result history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("Section snapshot history was dropped")
            db.execute("DELETE FROM plm.sol_section_create_results WHERE solution_section_id=%s", (section,))
            db.execute("DELETE FROM plm.sol_sections WHERE solution_section_id=%s", (section,))
        finally:
            db.execute("ALTER TABLE plm.sol_section_create_results "
                       "ENABLE TRIGGER trg_sol_section_create_results__owner")
            db.execute("ALTER TABLE plm.sol_sections ENABLE TRIGGER trg_sol_sections__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    print("SOL_04_A02_SECTION_CREATE_RESULT_SCHEMA_PASS: existing/empty upgrade, "
          "downgrade, drift, closed root/result, FK/check/duplicate/history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol04-section-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(prior.PG_SOURCE / name, install / name)
    shutil.copy2(prior.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(prior.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (prior.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    started = False
    try:
        prior.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                  "-A", "trust", "--no-locale", "-E", "UTF8")
        prior.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                  "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            prior.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol04-section-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
