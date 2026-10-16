"""Win11 disposable PG18 check of event-backed Reference eligibility Guard."""

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
    "reference_eligibility_schema_fixture",
    ROOT / "validation/sol-01-a16-p02-reference-eligibility-schema/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
helper = base.helper
rejects = base.rejects
PREVIOUS = "20261009_0152"
CURRENT = "20261009_0153"


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Eligibility Guard Actor','eligibility guard actor') "
            "RETURNING user_id").fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOLG16','solg16','Eligibility Guard',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
        root, version = uuid.uuid4(), uuid.uuid4()
        with db.transaction():
            db.execute(
                "INSERT INTO plm.sol_reference_solutions"
                "(reference_solution_id,scope,project_id,name,current_version_ref,created_by) "
                "VALUES (%s,'PROJECT',%s,'Guard root',%s,%s)",
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
        event = (
            "INSERT INTO plm.sol_reference_eligibility_events"
            "(eligibility_event_id,reference_solution_id,reference_version_id,"
            "scope,project_id,event_kind,prior_state,result_state,reason,actor_id,"
            "prior_lock_version,result_lock_version) "
            "VALUES (%s,%s,%s,'PROJECT',%s,'HUMAN',%s,%s,%s,%s,0,1)")
        values = (uuid.uuid4(), root, version, project, "REFERENCE_ONLY",
                  "ELIGIBLE", "Human reviewed", actor)
        rejects("Reference eligibility event mismatch", lambda: db.execute(
            "UPDATE plm.sol_reference_solutions SET eligibility_state='ELIGIBLE',"
            "eligibility_reason='Human reviewed',lock_version=1 "
            "WHERE reference_solution_id=%s", (root,)))
        rejects("Reference eligibility transaction is incomplete",
                lambda: db.execute(event, values))
        rejects("Reference eligibility event prior state mismatch",
                lambda: db.execute(event, (
                    uuid.uuid4(), root, version, project, "REVOKED", "ELIGIBLE",
                    "Human reviewed", actor)))
        with db.transaction():
            db.execute(event, values)
            db.execute(
                "UPDATE plm.sol_reference_solutions SET eligibility_state='ELIGIBLE',"
                "eligibility_reason='Human reviewed',lock_version=1 "
                "WHERE reference_solution_id=%s", (root,))
        row = db.execute(
            "SELECT eligibility_state,eligibility_reason,lock_version,current_version_ref "
            "FROM plm.sol_reference_solutions WHERE reference_solution_id=%s", (root,)).fetchone()
        assert row == ("ELIGIBLE", "Human reviewed", 1, version), row
        rejects("Reference eligibility event prior state mismatch",
                lambda: db.execute(event, values))
        rejects("Reference eligibility event prior state mismatch or immutable",
                lambda: db.execute(
                    "DELETE FROM plm.sol_reference_eligibility_events "
                    "WHERE eligibility_event_id=%s", (values[0],)))
        rejects("ReferenceSolution history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.sol_reference_eligibility_events"))
    rejects("Reference eligibility history prevents Guard downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))
    print("SOL_01_A16_P03_REFERENCE_ELIGIBILITY_GUARD_PG_PASS: empty/existing-v1/down/re-up, "
          "drift, v0 first decision, missing event/closure/direct DML/history refusal")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol01-eligibility-guard-pg-"))
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
                and scratch.name.startswith("plm-sol01-eligibility-guard-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
