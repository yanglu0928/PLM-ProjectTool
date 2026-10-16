"""Disposable Windows 11/PG18 proof for closed SOL-06 version root 0161."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_schema_fixture_for_sol06",
    ROOT / "validation/sol-01-a03-p02-section-version-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)

PREVIOUS = "20261009_0160"
TARGET = "20261012_0161"
TABLE = "plm.sol_structured_specs"


def rejects(expected: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + expected)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, TARGET)  # historical closed-guard contract
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
        assert db.execute(
            "SELECT tgname FROM pg_trigger WHERE tgrelid=%s::regclass "
            "AND NOT tgisinternal ORDER BY tgname", (TABLE,),
        ).fetchall() == [("trg_sol_specs__no_truncate",), ("trg_sol_specs__owner",)]
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('SOL06 schema actor','sol06 schema actor') RETURNING user_id",
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('SOL06PG','sol06pg','Existing project',%s) "
            "RETURNING project_id", (actor,),
        ).fetchone()[0]
    command.upgrade(cfg, TARGET)  # existing project data
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT name FROM plm.prj_projects WHERE project_id=%s",
                          (project,)).fetchone()[0] == "Existing project"
    command.downgrade(cfg, PREVIOUS)  # empty SOL-06 history with existing project
    command.upgrade(cfg, TARGET)

    series, version = uuid.uuid4(), uuid.uuid4()
    insert = (f"INSERT INTO {TABLE}(structured_solution_spec_id,spec_series_id,"
              "project_id,spec_type,version_no,content_fingerprint,created_by) "
              "VALUES (%s,%s,%s,%s,%s,%s,%s)")
    values = (version, series, project, "PROCESS_MODEL", 1, b"a" * 32, actor)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rejects("write Owner is not installed", lambda: db.execute(insert, values))
        rejects("history cannot be truncated", lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_sol_specs__owner")
        try:
            db.execute(insert, values)
            assert db.execute(f"SELECT spec_type FROM {TABLE} WHERE "
                              "structured_solution_spec_id=%s", (version,)
                              ).fetchone()[0] == "PROCESS_MODEL"
            rejects("ck_sol_specs__type", lambda: db.execute(insert, (
                uuid.uuid4(), uuid.uuid4(), project, "FREE_TEXT", 1,
                b"b" * 32, actor)))
            rejects("ck_sol_specs__number", lambda: db.execute(insert, (
                uuid.uuid4(), uuid.uuid4(), project, "PROCESS_MODEL", 0,
                b"b" * 32, actor)))
            rejects("ck_sol_specs__fingerprint", lambda: db.execute(insert, (
                uuid.uuid4(), uuid.uuid4(), project, "PROCESS_MODEL", 1,
                b"short", actor)))
            rejects("fk_sol_specs__project", lambda: db.execute(insert, (
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "PROCESS_MODEL", 1,
                b"b" * 32, actor)))
            rejects("uq_sol_specs__series_no", lambda: db.execute(insert, (
                uuid.uuid4(), series, project, "PROCESS_MODEL", 1,
                b"b" * 32, actor)))
            rejects("fk_sol_specs__supersedes", lambda: db.execute(
                f"INSERT INTO {TABLE}(spec_series_id,project_id,spec_type,"
                "version_no,content_fingerprint,supersedes_version_ref,created_by) "
                "VALUES (%s,%s,'INTERFACE_SPEC',2,%s,%s,%s)",
                (series, project, b"b" * 32, version, actor)))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_sol_specs__owner")
        rejects("write Owner is not installed", lambda: db.execute(
            f"UPDATE {TABLE} SET version_state='APPROVED' WHERE "
            "structured_solution_spec_id=%s", (version,)))
        rejects("write Owner is not installed", lambda: db.execute(
            f"DELETE FROM {TABLE} WHERE structured_solution_spec_id=%s", (version,)))
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1
    rejects("history prevents downgrade", lambda: command.downgrade(cfg, PREVIOUS))
    print("SOL_06_A02_STRUCTURED_SPEC_SCHEMA_PASS: empty/existing upgrade, "
          "empty downgrade/re-upgrade, DML closure, constraints, nonempty refusal "
          "at historical revision 0161")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol06-spec-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(fixture.PG_SOURCE / name, install / name)
    shutil.copy2(fixture.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(fixture.VECTOR_SOURCE / "vector.control",
                 install / "share/extension/vector.control")
    for path in (fixture.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = fixture.free_port()
    started = False
    try:
        fixture.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                    "-A", "trust", "--no-locale", "-E", "UTF8")
        fixture.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l",
                    str(scratch / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}",
                    "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            fixture.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                        "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol06-spec-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
