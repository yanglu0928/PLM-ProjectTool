"""Disposable PG18 proof of ReferenceVersion exact confirmation binding."""

from __future__ import annotations

import importlib.util
import shutil
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
    "prior_reference_schema", ROOT / "validation/sol-01-a03-p03-reference-source-schema/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
source = prior.prior


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + message)


def verify(port: int) -> None:
    prior.verify(port)
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.downgrade(cfg, "20261008_0142")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_normalized='section version actor'"
        ).fetchone()[0]
        project = db.execute(
            "SELECT project_id FROM plm.prj_projects WHERE project_code_normalized='solsec1'"
        ).fetchone()[0]
        digest = b"s" * 32
        confirmation = db.execute(
            "INSERT INTO plm.sol_reference_deidentification_confirmations("
            "source_fingerprint,source_project_class,deidentification_class,"
            "applicability,attestation_statement,confirmed_by,confirmed_at,expires_at,"
            "trace_id) VALUES (%s,'PLM','DEIDENTIFIED','{}'::jsonb,"
            "'I_VERIFIED_DEIDENTIFICATION',%s,statement_timestamp(),"
            "statement_timestamp()+interval '1 day',%s) RETURNING confirmation_id",
            (digest, actor, uuid.uuid4()),
        ).fetchone()[0]
        global_root, project_root = uuid.uuid4(), uuid.uuid4()
        rejects("ReferenceSolution Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_reference_solutions(scope,name,created_by) "
            "VALUES ('GLOBAL','Closed reference',%s)", (actor,)))
        for table in ("sol_reference_solutions", "sol_reference_versions"):
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER trg_{table}__owner")
        try:
            db.execute("INSERT INTO plm.sol_reference_solutions(reference_solution_id,"
                       "scope,name,created_by) VALUES (%s,'GLOBAL','Global reference',%s)",
                       (global_root, actor))
            db.execute("INSERT INTO plm.sol_reference_solutions(reference_solution_id,"
                       "scope,project_id,name,created_by) VALUES "
                       "(%s,'PROJECT',%s,'Project reference',%s)",
                       (project_root, project, actor))
            insert = (
                "INSERT INTO plm.sol_reference_versions(reference_solution_id,scope,"
                "project_id,version_no,applicability,source_project_class,"
                "deidentification_class,content_fingerprint,source_fingerprint,"
                "deidentification_confirmation_id,declared_document_count,"
                "declared_evidence_count,created_by) VALUES "
                "(%s,%s,%s,%s,'{}'::jsonb,'PLM','DEIDENTIFIED',%s,%s,%s,1,0,%s) "
                "RETURNING reference_version_id"
            )
            global_id = db.execute(insert, (global_root, "GLOBAL", None, 1,
                                            b"c" * 32, digest, confirmation, actor)).fetchone()[0]
            project_id = db.execute(insert, (project_root, "PROJECT", project, 1,
                                             b"p" * 32, b"q" * 32, None, actor)).fetchone()[0]
            rejects("fk_sol_reference_versions__confirmation_source", lambda: db.execute(
                insert, (global_root, "GLOBAL", None, 2, b"c" * 32,
                         b"x" * 32, confirmation, actor)))
            rejects("ck_sol_reference_versions__confirmation_scope", lambda: db.execute(
                insert, (global_root, "GLOBAL", None, 2, b"c" * 32,
                         digest, None, actor)))
            rejects("ck_sol_reference_versions__confirmation_scope", lambda: db.execute(
                insert, (project_root, "PROJECT", project, 2, b"p" * 32,
                         digest, confirmation, actor)))
            rejects("ck_sol_reference_versions__source_fingerprint", lambda: db.execute(
                insert, (project_root, "PROJECT", project, 2, b"p" * 32,
                         b"short", None, actor)))
            rejects("ReferenceVersion history requires reviewed source binding migration",
                    lambda: command.downgrade(cfg, "20261008_0142"))
            for table, column, ids in (
                ("sol_reference_versions", "reference_version_id", (global_id, project_id)),
                ("sol_reference_solutions", "reference_solution_id", (global_root, project_root)),
            ):
                for ident in ids:
                    db.execute(f"DELETE FROM plm.{table} WHERE {column}=%s", (ident,))
        finally:
            for table in ("sol_reference_versions", "sol_reference_solutions"):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER trg_{table}__owner")
    command.downgrade(cfg, "20261008_0142")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT source_fingerprint FROM plm."
                          "sol_reference_deidentification_confirmations "
                          "WHERE confirmation_id=%s", (confirmation,)).fetchone()[0] == digest
        legacy_root = uuid.uuid4()
        for table in ("sol_reference_solutions", "sol_reference_versions"):
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER trg_{table}__owner")
        try:
            db.execute("INSERT INTO plm.sol_reference_solutions(reference_solution_id,"
                       "scope,project_id,name,created_by) VALUES "
                       "(%s,'PROJECT',%s,'Legacy reference',%s)",
                       (legacy_root, project, actor))
            db.execute("INSERT INTO plm.sol_reference_versions(reference_solution_id,scope,"
                       "project_id,version_no,applicability,source_project_class,"
                       "deidentification_class,content_fingerprint,declared_document_count,"
                       "declared_evidence_count,created_by) VALUES "
                       "(%s,'PROJECT',%s,1,'{}'::jsonb,'PLM','DEIDENTIFIED',%s,1,0,%s)",
                       (legacy_root, project, b"l" * 32, actor))
            rejects("ReferenceVersion history requires reviewed source binding migration",
                    lambda: command.upgrade(cfg, "head"))
            assert db.execute("SELECT count(*) FROM plm.sol_reference_versions "
                              "WHERE reference_solution_id=%s", (legacy_root,)).fetchone()[0] == 1
            db.execute("DELETE FROM plm.sol_reference_versions WHERE reference_solution_id=%s",
                       (legacy_root,))
            db.execute("DELETE FROM plm.sol_reference_solutions WHERE reference_solution_id=%s",
                       (legacy_root,))
        finally:
            for table in ("sol_reference_versions", "sol_reference_solutions"):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER trg_{table}__owner")
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_01_A04_P03_P01_CONFIRMATION_BINDING_SCHEMA_PASS: composite source FK, "
          "scope and history guards, populated legacy rejection, downgrade/re-upgrade, drift")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-ref-binding-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(source.PG_SOURCE / name, install / name)
    shutil.copy2(source.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(source.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (source.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = source.free_port()
    started = False
    try:
        source.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        source.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                   "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            source.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-ref-binding-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
