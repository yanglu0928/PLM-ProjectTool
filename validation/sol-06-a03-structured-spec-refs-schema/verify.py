"""Disposable Windows 11/PG18 proof for closed SOL-06 reference collections."""

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
    "sol06_a02_fixture", ROOT / "validation/sol-06-a02-structured-spec-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
TABLES = (
    "sol_spec_requirement_refs", "sol_spec_section_refs",
    "sol_spec_evidence_refs", "sol_spec_artifact_refs",
)
PREVIOUS = "20261012_0161"
TARGET = "20261012_0162"


def rejects(expected: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + expected)


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, TARGET)  # historical closed-guard contract
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        for table in TABLES:
            assert db.execute(f"SELECT count(*) FROM plm.{table}").fetchone()[0] == 0
            assert len(db.execute(
                "SELECT tgname FROM pg_trigger WHERE tgrelid=%s::regclass "
                "AND NOT tgisinternal", (f"plm.{table}",)).fetchall()) == 2
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        for table in TABLES:
            assert db.execute("SELECT to_regclass(%s)", (f"plm.{table}",)).fetchone()[0] is None
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('SOL06 ref actor','sol06 ref actor') RETURNING user_id").fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOL06REF','sol06ref','Existing project',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
    command.upgrade(cfg, TARGET)  # existing project data
    command.downgrade(cfg, PREVIOUS)  # empty child history
    command.upgrade(cfg, TARGET)

    series, version, artifact = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_structured_specs DISABLE TRIGGER trg_sol_specs__owner")
        try:
            db.execute(
                "INSERT INTO plm.sol_structured_specs("
                "structured_solution_spec_id,spec_series_id,project_id,spec_type,"
                "version_no,content_fingerprint,created_by) "
                "VALUES (%s,%s,%s,'PROCESS_MODEL',1,%s,%s)",
                (version, series, project, b"a" * 32, actor))
        finally:
            db.execute("ALTER TABLE plm.sol_structured_specs ENABLE TRIGGER trg_sol_specs__owner")
        for table in TABLES:
            insert = (f"INSERT INTO plm.{table}(structured_solution_spec_id,"
                      "spec_series_id,project_id,ordinal," + {
                          TABLES[0]: "requirement_id,requirement_version_id",
                          TABLES[1]: "solution_section_id,solution_section_version_id",
                          TABLES[2]: "evidence_id",
                          TABLES[3]: "output_artifact_id",
                      }[table] + ") VALUES (" + {
                          TABLES[0]: "%s,%s,%s,%s,%s,%s)",
                          TABLES[1]: "%s,%s,%s,%s,%s,%s)",
                          TABLES[2]: "%s,%s,%s,%s,%s)",
                          TABLES[3]: "%s,%s,%s,%s,%s)",
                      }[table])
            values = (version, series, project, 1) + (
                (uuid.uuid4(), uuid.uuid4()) if table in TABLES[:2]
                else (artifact,))
            rejects("reference Owner is not installed", lambda: db.execute(insert, values))
            rejects("reference history cannot be truncated",
                    lambda: db.execute(f"TRUNCATE plm.{table}"))
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER trg_{table}__owner")
            try:
                rejects("ordinal", lambda: db.execute(insert, values[:3] + (0,) + values[4:]))
                rejects("__spec", lambda: db.execute(
                    insert, (uuid.uuid4(), series, project) + values[3:]))
                if table == TABLES[0]:
                    rejects("__requirement", lambda: db.execute(insert, values))
                elif table == TABLES[1]:
                    rejects("__section", lambda: db.execute(insert, values))
                elif table == TABLES[2]:
                    rejects("__evidence", lambda: db.execute(insert, values))
                else:
                    rejects("__identity", lambda: db.execute(
                        insert, values[:-1] + (uuid.UUID(int=0),)))
                    db.execute(insert, values)
                    rejects("__version_ordinal", lambda: db.execute(
                        insert, values[:-1] + (uuid.uuid4(),)))
                    rejects("__version_artifact", lambda: db.execute(
                        insert, values[:3] + (2, artifact)))
            finally:
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER trg_{table}__owner")
            if table == TABLES[3]:
                rejects("reference Owner is not installed", lambda: db.execute(
                    f"DELETE FROM plm.{table} WHERE structured_solution_spec_id=%s", (version,)))
    rejects("reference history prevents downgrade", lambda: command.downgrade(cfg, PREVIOUS))
    print("SOL_06_A03_STRUCTURED_SPEC_REFS_SCHEMA_PASS: empty/existing upgrade, "
          "empty downgrade/re-upgrade, closed DML, FK/ordinal/duplicate, "
          "nonempty refusal at historical revision 0162")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol06-refs-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(fixture.fixture.PG_SOURCE / name, install / name)
    shutil.copy2(fixture.fixture.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(fixture.fixture.VECTOR_SOURCE / "vector.control",
                 install / "share/extension/vector.control")
    for path in (fixture.fixture.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = fixture.fixture.free_port()
    started = False
    try:
        fixture.fixture.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                            "-A", "trust", "--no-locale", "-E", "UTF8")
        fixture.fixture.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l",
                            str(scratch / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}",
                            "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            fixture.fixture.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                                "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol06-refs-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
