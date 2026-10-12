"""Disposable Windows 11/PG18 proof for closed SOL-06 typed payload 0163."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_a03_fixture", ROOT / "validation/sol-06-a03-structured-spec-refs-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
PREVIOUS = "20261012_0162"
TABLE = "plm.sol_spec_payloads"


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
    command.upgrade(cfg, "head")  # empty database
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
        assert len(db.execute(
            "SELECT tgname FROM pg_trigger WHERE tgrelid=%s::regclass "
            "AND NOT tgisinternal", (TABLE,)).fetchall()) == 2
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('SOL06 payload actor','sol06 payload actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOL06PAY','sol06pay','Existing project',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
    command.upgrade(cfg, "head")  # existing business rows
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)  # empty payload history
    command.upgrade(cfg, "head")
    command.check(cfg)

    series, version = uuid.uuid4(), uuid.uuid4()
    insert = (f"INSERT INTO {TABLE}(structured_solution_spec_id,spec_series_id,"
              "project_id,spec_type,schema_version,payload_json,payload_fingerprint) "
              "VALUES (%s,%s,%s,%s,%s,%s,%s)")
    values = (version, series, project, "PROCESS_MODEL", 1,
              Jsonb({"nodes": [{"key": "start"}]}), b"b" * 32)
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
        rejects("payload Owner is not installed", lambda: db.execute(insert, values))
        rejects("payload history cannot be truncated", lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_sol_spec_payloads__owner")
        try:
            rejects("fk_sol_spec_payloads__spec", lambda: db.execute(
                insert, (uuid.uuid4(),) + values[1:]))
            rejects("fk_sol_spec_payloads__spec", lambda: db.execute(
                insert, (version, series, uuid.uuid4()) + values[3:]))
            rejects("fk_sol_spec_payloads__spec", lambda: db.execute(
                insert, values[:3] + ("INTERFACE_SPEC",) + values[4:]))
            rejects("ck_sol_spec_payloads__schema_version", lambda: db.execute(
                insert, values[:4] + (2,) + values[5:]))
            rejects("ck_sol_spec_payloads__object", lambda: db.execute(
                insert, values[:5] + (Jsonb({}),) + values[6:]))
            rejects("ck_sol_spec_payloads__object", lambda: db.execute(
                insert, values[:5] + (Jsonb([1]),) + values[6:]))
            rejects("ck_sol_spec_payloads__size", lambda: db.execute(
                insert, values[:5] + (Jsonb({"body": "x" * 1048576}),) + values[6:]))
            rejects("ck_sol_spec_payloads__fingerprint", lambda: db.execute(
                insert, values[:6] + (b"short",)))
            db.execute(insert, values)
            rejects("pk_sol_spec_payloads", lambda: db.execute(insert, values))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_sol_spec_payloads__owner")
        rejects("payload Owner is not installed", lambda: db.execute(
            f"UPDATE {TABLE} SET schema_version=1 WHERE structured_solution_spec_id=%s",
            (version,)))
        rejects("payload Owner is not installed", lambda: db.execute(
            f"DELETE FROM {TABLE} WHERE structured_solution_spec_id=%s", (version,)))
    rejects("payload history prevents downgrade", lambda: command.downgrade(cfg, PREVIOUS))
    command.check(cfg)
    print("SOL_06_A05_STRUCTURED_SPEC_PAYLOAD_SCHEMA_PASS: empty/existing upgrade, "
          "empty downgrade/re-upgrade, DML closure, composite FK/type/shape/size/unique, "
          "nonempty refusal, drift")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol06-payload-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    pg = fixture.fixture.fixture
    for name in ("bin", "lib", "share"):
        shutil.copytree(pg.PG_SOURCE / name, install / name)
    shutil.copy2(pg.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(pg.VECTOR_SOURCE / "vector.control",
                 install / "share/extension/vector.control")
    for path in (pg.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = pg.free_port()
    started = False
    try:
        pg.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
               "-A", "trust", "--no-locale", "-E", "UTF8")
        pg.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l",
               str(scratch / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}",
               "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            pg.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                   "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol06-payload-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
