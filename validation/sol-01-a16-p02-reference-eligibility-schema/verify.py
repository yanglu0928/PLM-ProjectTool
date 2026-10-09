"""Win11 disposable PG18 proof of closed Reference eligibility event schema."""

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
    "reference_schema_fixture",
    ROOT / "validation/sol-01-a06-reference-revise-result-schema/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
helper = base.prior
PREVIOUS = "20261009_0151"
CURRENT = "20261009_0152"
TABLE = "plm.sol_reference_eligibility_events"
TRIGGER = "trg_sol_reference_eligibility_events__owner"


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

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Eligibility Schema Actor','eligibility schema actor') "
            "RETURNING user_id").fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOLE16','sole16','Eligibility migration',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
        root, version = uuid.uuid4(), uuid.uuid4()
        with db.transaction():
            db.execute(
                "INSERT INTO plm.sol_reference_solutions"
                "(reference_solution_id,scope,project_id,name,current_version_ref,created_by) "
                "VALUES (%s,'PROJECT',%s,'Eligibility root',%s,%s)",
                (root, project, version, actor))
            db.execute(
                "INSERT INTO plm.sol_reference_versions"
                "(reference_version_id,reference_solution_id,scope,project_id,version_no,"
                "applicability,source_project_class,deidentification_class,"
                "content_fingerprint,source_fingerprint,declared_document_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,'PROJECT',%s,1,'{}'::jsonb,'PLM','INTERNAL',"
                "%s,%s,1,0,%s)",
                (version, root, project, b"c" * 32, b"s" * 32, actor))
    command.upgrade(cfg, CURRENT)
    command.check(cfg)

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        insert = (
            f"INSERT INTO {TABLE}(eligibility_event_id,reference_solution_id,"
            "reference_version_id,scope,project_id,event_kind,prior_state,"
            "result_state,reason,actor_id,prior_lock_version,result_lock_version) "
            "VALUES (%s,%s,%s,'PROJECT',%s,%s,%s,%s,%s,%s,1,2)")
        valid = (uuid.uuid4(), root, version, project, "HUMAN", "REFERENCE_ONLY",
                 "ELIGIBLE", "Reviewed", actor)
        rejects("Reference eligibility Owner is not installed",
                lambda: db.execute(insert, valid))
        rejects("Reference revision pointer mismatch",
                lambda: db.execute(
                    "UPDATE plm.sol_reference_solutions SET eligibility_state='ELIGIBLE',"
                    "lock_version=2 WHERE reference_solution_id=%s", (root,)))
        rejects("ReferenceSolution history cannot be truncated",
                lambda: db.execute(f"TRUNCATE {TABLE}"))
        # Test-only trigger bypass: prove SQL constraints and downgrade history
        # refusal without pretending the future controlled Owner is installed.
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            rejects("ck_sol_reference_eligibility__transition",
                    lambda: db.execute(insert, (
                        uuid.uuid4(), root, version, project, "HUMAN", "REVOKED",
                        "ELIGIBLE", "Reviewed", actor)))
            rejects("ck_sol_reference_eligibility__reason",
                    lambda: db.execute(insert, (
                        uuid.uuid4(), root, version, project, "HUMAN", "REFERENCE_ONLY",
                        "ELIGIBLE", " ", actor)))
            rejects("fk_sol_reference_eligibility__version",
                    lambda: db.execute(insert, (
                        uuid.uuid4(), root, uuid.uuid4(), project, "HUMAN",
                        "REFERENCE_ONLY", "ELIGIBLE", "Reviewed", actor)))
            db.execute(insert, valid)
            rejects("uq_sol_reference_eligibility__root_lock",
                    lambda: db.execute(insert, (
                        uuid.uuid4(), root, version, project, "HUMAN",
                        "REFERENCE_ONLY", "RESTRICTED", "Reviewed", actor)))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
        rejects("Reference eligibility Owner is not installed",
                lambda: db.execute(f"DELETE FROM {TABLE}"))
        rejects("Reference eligibility Owner is not installed",
                lambda: db.execute(f"UPDATE {TABLE} SET reason='Changed'"))
    rejects("Reference eligibility history prevents downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))

    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            db.execute(f"DELETE FROM {TABLE}")
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_reference_solutions "
                   "DISABLE TRIGGER trg_sol_reference_solutions__owner")
        try:
            db.execute("UPDATE plm.sol_reference_solutions "
                       "SET eligibility_state='ELIGIBLE',eligibility_reason='Unknown' "
                       "WHERE reference_solution_id=%s", (root,))
        finally:
            db.execute("ALTER TABLE plm.sol_reference_solutions "
                       "ENABLE TRIGGER trg_sol_reference_solutions__owner")
    rejects("Reference eligibility history requires audited forward repair",
            lambda: command.upgrade(cfg, CURRENT))
    print("SOL_01_A16_P02_REFERENCE_ELIGIBILITY_SCHEMA_PASS: empty/existing upgrade, "
          "down/re-up, drift, closed DML/constraints/history refusal")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol01-eligibility-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(helper.PG_SOURCE / name, install / name)
    shutil.copy2(helper.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(helper.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (helper.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    started = False
    try:
        helper.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        helper.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            helper.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol01-eligibility-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
