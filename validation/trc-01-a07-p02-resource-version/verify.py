"""Disposable PostgreSQL 18 TraceLink version migration and history proof."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, USER = "127.0.0.1", "poc_admin"
ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"


def run(*args: str, detached: bool = False) -> None:
    result = subprocess.run(
        args, stdout=subprocess.DEVNULL if detached else subprocess.PIPE,
        stderr=subprocess.DEVNULL if detached else subprocess.PIPE,
        text=True, timeout=120,
    )
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def migration(name: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    ))


def rejected(db, statement: str, params: tuple) -> None:
    try:
        db.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError("invalid TraceLink resource version mutation accepted")


def insert_edge(db, actor: uuid.UUID, project: uuid.UUID) -> uuid.UUID:
    return db.execute(
        "INSERT INTO plm.trc_links(scope,project_id,source_owner_module,"
        "source_object_type,source_object_id,source_version_id,source_project_id,"
        "target_owner_module,target_object_type,target_object_id,target_version_id,"
        "target_project_id,relation_type,created_by,trace_id) VALUES "
        "('PROJECT',%s,'document','DOC-02',%s,%s,%s,"
        "'document','DOC-02',%s,%s,%s,'DERIVED_FROM',%s,%s) "
        "RETURNING trace_link_id",
        (project, uuid.uuid4(), uuid.uuid4(), project,
         uuid.uuid4(), uuid.uuid4(), project, actor, uuid.uuid4()),
    ).fetchone()[0]


def seed(name: str) -> tuple[uuid.UUID, uuid.UUID]:
    with connect(name) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id",
            (f"Synthetic Trace {name}", f"synthetic trace {name}"),
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES (%s,%s,'Synthetic Trace',%s) "
            "RETURNING project_id", ("TRC1", "trc1", actor),
        ).fetchone()[0]
        return actor, project


def verify_db(admin, name: str, kind: str) -> None:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    cfg = migration(name)
    try:
        if kind == "empty":
            command.upgrade(cfg, "head")
            with connect(name) as db:
                assert db.execute(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='plm' AND table_name='trc_links' "
                    "AND column_name='lock_version'",
                ).fetchone()[0] == 1
            command.downgrade(cfg, "20261001_0052")
            command.upgrade(cfg, "head")
            command.check(cfg)
            return

        command.upgrade(cfg, "20261001_0052")
        actor, project = seed(name)
        with connect(name) as db:
            active = insert_edge(db, actor, project)
            revoked = insert_edge(db, actor, project)
            if kind == "terminal":
                superseded = insert_edge(db, actor, project)
                replacement = insert_edge(db, actor, project)
                db.execute(
                    "UPDATE plm.trc_links SET link_state='REVOKED' "
                    "WHERE trace_link_id=%s", (revoked,),
                )
                db.execute(
                    "UPDATE plm.trc_links SET link_state='SUPERSEDED',"
                    "superseded_by_ref=%s WHERE trace_link_id=%s",
                    (replacement, superseded),
                )
        command.upgrade(cfg, "head")
        with connect(name) as db:
            versions = dict(db.execute(
                "SELECT trace_link_id,lock_version FROM plm.trc_links",
            ).fetchall())
            assert versions[active] == 0
            assert versions[revoked] == (1 if kind == "terminal" else 0)
            if kind == "terminal":
                assert versions[superseded] == 1
                assert versions[replacement] == 0
                rejected(db, "UPDATE plm.trc_links SET lock_version=7 "
                         "WHERE trace_link_id=%s", (active,))
                rejected(db, "UPDATE plm.trc_links SET link_state='ACTIVE' "
                         "WHERE trace_link_id=%s", (revoked,))
                db.execute("UPDATE plm.trc_links SET link_state='REVOKED' "
                           "WHERE trace_link_id=%s", (active,))
                assert db.execute("SELECT lock_version FROM plm.trc_links "
                                  "WHERE trace_link_id=%s", (active,)).fetchone()[0] == 1
                rejected(db, "UPDATE plm.trc_links SET link_state='REVOKED' "
                         "WHERE trace_link_id=%s", (active,))
            else:
                rejected(db, "UPDATE plm.trc_links SET lock_version=7 "
                         "WHERE trace_link_id=%s", (active,))
        if kind == "terminal":
            try:
                command.downgrade(cfg, "20261001_0052")
            except Exception as exc:
                assert "terminal version history prevents downgrade" in str(exc)
            else:
                raise AssertionError("terminal TraceLink history downgraded")
            with connect(name) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20261002_0053"
                assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 4
        else:
            command.downgrade(cfg, "20261001_0052")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='plm' AND table_name='trc_links' "
                    "AND column_name='lock_version'",
                ).fetchone()[0] == 0
            command.upgrade(cfg, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.trc_links "
                                  "WHERE lock_version=0 AND link_state='ACTIVE'").fetchone()[0] == 2
    finally:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def verify() -> None:
    with connect("postgres") as admin:
        for kind in ("empty", "active", "terminal"):
            verify_db(admin, f"trace_version_{kind}_{uuid.uuid4().hex[:8]}", kind)
    print("PASS: TraceLink empty/active/terminal history migration, guards and safe downgrade")


def main() -> None:
    global PORT
    scratch = Path(tempfile.mkdtemp(prefix="plm-trc-version-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install, data = scratch / "pgsql", scratch / "data"
    bin_dir = install / "bin"
    started = False
    try:
        for part in ("bin", "lib", "share"):
            shutil.copytree(PG_SOURCE / part, install / part)
        shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
        shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
        for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
            shutil.copy2(path, install / "share/extension" / path.name)
        with socket.socket() as probe:
            probe.bind((HOST, 0))
            PORT = int(probe.getsockname()[1])
        run(str(bin_dir / "initdb.exe"), "-D", str(data), "-U", USER,
            "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(bin_dir / "pg_ctl.exe"), "-D", str(data),
            "-l", str(scratch / "postgres.log"),
            "-o", f"-h {HOST} -p {PORT}", "-w", "start", detached=True)
        started = True
        verify()
    finally:
        if started:
            run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        if data.exists():
            status = subprocess.run(
                [str(bin_dir / "pg_ctl.exe"), "-D", str(data), "status"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
            )
            if status.returncode == 0:
                raise RuntimeError(f"isolated PostgreSQL remains running at {scratch}")
        if scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) \
                and scratch.name.startswith("plm-trc-version-pg-"):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
