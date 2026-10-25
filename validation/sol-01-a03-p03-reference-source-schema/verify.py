"""Disposable PG18 proof for closed ReferenceSolution Schema0139."""

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
PRIOR = ROOT / "validation/sol-01-a03-p02-section-version-schema/verify.py"
SPEC = importlib.util.spec_from_file_location("prior_section_verifier", PRIOR)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
PREVIOUS = "20261008_0138"
TABLES = ("sol_reference_solutions", "sol_reference_versions",
          "sol_reference_document_refs", "sol_reference_evidence_refs")


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def verify(port: int) -> None:
    # The prior verifier exercises existing-data upgrade, empty downgrade/re-upgrade,
    # drift, and earlier Solution constraints against the current Alembic head.
    prior.verify(port)
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    # Exercise the original 0139 schema before later binding columns are added.
    command.downgrade(cfg, "20261008_0139")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_normalized='section version actor'"
        ).fetchone()[0]
        project = db.execute(
            "SELECT project_id FROM plm.prj_projects WHERE project_code_normalized='solsec1'"
        ).fetchone()[0]
        document_version = db.execute(
            "SELECT document_version_id FROM plm.doc_document_versions WHERE project_id=%s",
            (project,)).fetchone()[0]
        evidence = db.execute(
            "SELECT evidence_id FROM plm.evd_evidence_records WHERE project_id=%s",
            (project,)).fetchone()[0]
        reference, other_reference = uuid.uuid4(), uuid.uuid4()
        version = uuid.uuid4()
        rejects("ReferenceSolution Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_reference_solutions(scope,project_id,name,created_by) "
            "VALUES ('PROJECT',%s,'Reference',%s)", (project, actor)))
        rejects("ReferenceSolution history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.sol_reference_document_refs"))

        for table in TABLES:
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER trg_{table}__owner")
        try:
            db.execute(
                "INSERT INTO plm.sol_reference_solutions(reference_solution_id,scope,project_id,name,created_by) "
                "VALUES (%s,'PROJECT',%s,'Reference',%s),(%s,'PROJECT',%s,'Other',%s)",
                (reference, project, actor, other_reference, project, actor))
            rejects("ck_sol_references__scope", lambda: db.execute(
                "INSERT INTO plm.sol_reference_solutions(scope,project_id,name,created_by) "
                "VALUES ('GLOBAL',%s,'Wrong scope',%s)", (project, actor)))
            db.execute(
                "INSERT INTO plm.sol_reference_solutions(scope,name,created_by) "
                "VALUES ('GLOBAL','Global reference',%s)", (actor,))
            version_insert = (
                "INSERT INTO plm.sol_reference_versions(reference_version_id,reference_solution_id,"
                "scope,project_id,version_no,applicability,source_project_class,"
                "deidentification_class,content_fingerprint,declared_document_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,%s,%s,%s,'{}'::jsonb,'PLM','DEIDENTIFIED',%s,1,1,%s)"
            )
            db.execute(version_insert, (version, reference, "PROJECT", project, 1, b"r" * 32, actor))
            rejects("fk_sol_reference_versions__parent", lambda: db.execute(
                version_insert, (uuid.uuid4(), reference, "GLOBAL", None, 2, b"r" * 32, actor)))
            rejects("ck_sol_reference_versions__fingerprint", lambda: db.execute(
                version_insert, (uuid.uuid4(), other_reference, "PROJECT", project, 1, b"bad", actor)))
            db.execute(
                "INSERT INTO plm.sol_reference_document_refs(reference_version_id,"
                "reference_solution_id,scope,document_version_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,1)", (version, reference, document_version))
            rejects("uq_sol_reference_documents__version_document", lambda: db.execute(
                "INSERT INTO plm.sol_reference_document_refs(reference_version_id,"
                "reference_solution_id,scope,document_version_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,2)", (version, reference, document_version)))
            rejects("fk_sol_reference_documents__document", lambda: db.execute(
                "INSERT INTO plm.sol_reference_document_refs(reference_version_id,"
                "reference_solution_id,scope,document_version_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,2)", (version, reference, uuid.uuid4())))
            db.execute(
                "INSERT INTO plm.sol_reference_evidence_refs(reference_version_id,"
                "reference_solution_id,scope,evidence_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,1)", (version, reference, evidence))
            rejects("fk_sol_reference_evidence__evidence", lambda: db.execute(
                "INSERT INTO plm.sol_reference_evidence_refs(reference_version_id,"
                "reference_solution_id,scope,evidence_id,ordinal) "
                "VALUES (%s,%s,'PROJECT',%s,2)", (version, reference, uuid.uuid4())))
            rejects("fk_sol_references__current_version", lambda: db.execute(
                "UPDATE plm.sol_reference_solutions SET current_version_ref=%s "
                "WHERE reference_solution_id=%s", (version, other_reference)))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "ReferenceSolution history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("ReferenceSolution history was dropped")
            db.execute("DELETE FROM plm.sol_reference_evidence_refs")
            db.execute("DELETE FROM plm.sol_reference_document_refs")
            db.execute("DELETE FROM plm.sol_reference_versions")
            db.execute("DELETE FROM plm.sol_reference_solutions")
        finally:
            for table in reversed(TABLES):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER trg_{table}__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_01_A03_P03_REFERENCE_SOURCE_SCHEMA_PASS: prior regression, existing/empty "
          "upgrade, downgrade, drift, scope/source refs and history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-reference-pg-"))
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
    port = prior.free_port()
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
                and scratch.name.startswith("plm-sol-reference-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
