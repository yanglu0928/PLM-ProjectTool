"""Disposable Win11 PostgreSQL 18 proof for closed Outline/Reference links."""

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
PREVIOUS = "20261009_0153"
CURRENT = "20261009_0154"
TABLE = "plm.sol_outline_reference_refs"
TRIGGER = "trg_sol_outline_reference_refs__owner"


def run(*args: str, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(args, stdout=output, stderr=output, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def rejects(fragment: str, operation) -> None:
    try:
        operation()
    except Exception as error:
        if fragment not in str(error):
            raise AssertionError(f"expected {fragment!r}: {error}") from error
    else:
        raise AssertionError(f"expected rejection: {fragment}")


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)

    outline, version = uuid.uuid4(), uuid.uuid4()
    project, other_project = uuid.uuid4(), uuid.uuid4()
    actor = uuid.uuid4()
    project_ref, project_ref_ver = uuid.uuid4(), uuid.uuid4()
    other_ref, other_ref_ver = uuid.uuid4(), uuid.uuid4()
    global_ref, global_ref_ver = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        # Synthetic upstream roots are inserted before upgrade; the product's
        # separate Owners remain closed and are not claimed as part of A03.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'Reference schema actor','reference schema actor')", (actor,))
            for ident, code in ((project, "SOLA03A"), (other_project, "SOLA03B")):
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,"
                    "name,created_by) VALUES (%s,%s,%s,%s,%s)",
                    (ident, code, code.lower(), code, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Outline link',%s)", (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_outline_versions(solution_outline_version_id,solution_outline_id,"
                "project_id,version_no,content_fingerprint,missing_declarations,"
                "conflict_declarations,declared_section_count,declared_requirement_count,created_by) "
                "VALUES (%s,%s,%s,1,%s,'[]'::jsonb,'[]'::jsonb,0,0,%s)",
                (version, outline, project, b"v" * 32, actor))
            for root, ref_version, scope, source_project, number in (
                (project_ref, project_ref_ver, "PROJECT", project, 1),
                (other_ref, other_ref_ver, "PROJECT", other_project, 2),
                (global_ref, global_ref_ver, "GLOBAL", None, 3),
            ):
                db.execute(
                    "INSERT INTO plm.sol_reference_solutions(reference_solution_id,scope,"
                    "project_id,name,created_by) VALUES (%s,%s,%s,%s,%s)",
                    (root, scope, source_project, f"Reference {number}", actor))
                db.execute(
                    "INSERT INTO plm.sol_reference_versions(reference_version_id,"
                    "reference_solution_id,scope,project_id,version_no,applicability,"
                    "source_project_class,deidentification_class,content_fingerprint,"
                    "source_fingerprint,deidentification_confirmation_id,declared_document_count,"
                    "declared_evidence_count,created_by) VALUES "
                    "(%s,%s,%s,%s,1,'{}'::jsonb,'PLM','INTERNAL',%s,%s,%s,1,0,%s)",
                    (ref_version, root, scope, source_project, b"c" * 32,
                     b"s" * 32, uuid.uuid4() if scope == "GLOBAL" else None, actor))
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT declared_reference_count FROM plm.sol_outline_versions "
            "WHERE solution_outline_version_id=%s", (version,)).fetchone()[0] == 0
        insert = (f"INSERT INTO {TABLE}(solution_outline_version_id,solution_outline_id,"
                  "project_id,reference_solution_id,reference_version_id,reference_scope,"
                  "source_project_id,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)")
        project_link = (version, outline, project, project_ref, project_ref_ver,
                        "PROJECT", project, 1)
        global_link = (version, outline, project, global_ref, global_ref_ver,
                       "GLOBAL", None, 2)
        rejects("SolutionOutlineVersion Owner is not installed",
                lambda: db.execute(insert, project_link))
        rejects("SolutionOutlineVersion history cannot be truncated",
                lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            db.execute(insert, project_link)
            db.execute(insert, global_link)
            rejects("uq_sol_outline_references__version_ordinal",
                    lambda: db.execute(insert, global_link[:-1] + (1,)))
            rejects("uq_sol_outline_references__version_reference",
                    lambda: db.execute(insert, project_link[:-1] + (3,)))
            rejects("ck_sol_outline_references__ordinal",
                    lambda: db.execute(insert, project_link[:-1] + (0,)))
            rejects("ck_sol_outline_references__scope_project",
                    lambda: db.execute(insert, (
                        version, outline, project, other_ref, other_ref_ver,
                        "PROJECT", other_project, 3)))
            rejects("fk_sol_outline_references__project_source",
                    lambda: db.execute(insert, (
                        version, outline, project, other_ref, other_ref_ver,
                        "PROJECT", project, 3)))
            rejects("fk_sol_outline_references__reference",
                    lambda: db.execute(insert, (
                        version, outline, project, project_ref, uuid.uuid4(),
                        "PROJECT", project, 3)))
            rejects("fk_sol_outline_references__version",
                    lambda: db.execute(insert, (
                        uuid.uuid4(), outline, project, project_ref, project_ref_ver,
                        "PROJECT", project, 3)))
            rejects("ck_sol_outline_references__scope_project",
                    lambda: db.execute(insert, (
                        version, outline, project, global_ref, global_ref_ver,
                        "GLOBAL", project, 3)))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
        rejects("SolutionOutlineVersion Owner is not installed",
                lambda: db.execute(f"DELETE FROM {TABLE}"))
        rejects("SolutionOutlineVersion Owner is not installed",
                lambda: db.execute(f"UPDATE {TABLE} SET ordinal=3"))
    rejects("Outline reference history prevents downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        db.execute(f"DELETE FROM {TABLE}")
        db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
        db.execute("ALTER TABLE plm.sol_outline_versions "
                   "DISABLE TRIGGER trg_sol_outline_versions__owner")
        db.execute("UPDATE plm.sol_outline_versions SET declared_reference_count=1 "
                   "WHERE solution_outline_version_id=%s", (version,))
        db.execute("ALTER TABLE plm.sol_outline_versions "
                   "ENABLE TRIGGER trg_sol_outline_versions__owner")
    rejects("Outline reference count history prevents downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_outline_versions "
                   "DISABLE TRIGGER trg_sol_outline_versions__owner")
        db.execute("UPDATE plm.sol_outline_versions SET declared_reference_count=0 "
                   "WHERE solution_outline_version_id=%s", (version,))
        db.execute("ALTER TABLE plm.sol_outline_versions "
                   "ENABLE TRIGGER trg_sol_outline_versions__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    print("SOL_03_A03_OUTLINE_REFERENCE_SCHEMA_PASS: empty/existing upgrade, "
          "downgrade/re-up, drift, project/GLOBAL fixed FKs, order, closed DML, history refusal")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol03-reference-pg-"))
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
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol03-reference-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
