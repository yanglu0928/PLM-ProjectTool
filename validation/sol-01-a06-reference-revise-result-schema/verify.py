"""Win11 disposable PG18 proof for closed SOL_REFERENCE_REVISE result storage."""

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
    "section_result_schema", ROOT / "validation/sol-04-a02-section-create-result-schema/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
prior = base.prior
PREVIOUS = "20261009_0148"
CURRENT = "20261009_0149"


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    root, first, revised = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('SOL01 Revise Actor','sol01 revise actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOL01R','sol01r','Reference revise project',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
        with db.transaction():
            db.execute("INSERT INTO plm.sol_reference_solutions"
                       "(reference_solution_id,scope,project_id,name,current_version_ref,created_by) "
                       "VALUES (%s,'PROJECT',%s,'Reference root',%s,%s)",
                       (root, project, first, actor))
            for version_id, number, supersedes in ((first, 1, None), (revised, 2, first)):
                db.execute("INSERT INTO plm.sol_reference_versions"
                           "(reference_version_id,reference_solution_id,scope,project_id,version_no,"
                           "applicability,source_project_class,deidentification_class,"
                           "content_fingerprint,source_fingerprint,declared_document_count,"
                           "declared_evidence_count,supersedes_version_ref,created_by) "
                           "VALUES (%s,%s,'PROJECT',%s,%s,'{}'::jsonb,'TYPE','INTERNAL',"
                           "%s,%s,1,0,%s,%s)",
                           (version_id, root, project, number, b"c" * 32, b"s" * 32,
                            supersedes, actor))
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        statement = ("INSERT INTO plm.sol_reference_revise_results"
                     "(reference_version_id,reference_solution_id,scope,version_no,"
                     "supersedes_version_ref,content_fingerprint,source_fingerprint,created_at) "
                     "VALUES (%s,%s,'PROJECT',%s,%s,%s,%s,now())")
        values = (revised, root, 2, first, b"c" * 32, b"s" * 32)
        prior.rejects("ReferenceSolution revise Owner is not installed",
                      lambda: db.execute(
                          "INSERT INTO plm.sol_reference_versions"
                          "(reference_version_id,reference_solution_id,scope,project_id,version_no,"
                          "applicability,source_project_class,deidentification_class,"
                          "content_fingerprint,source_fingerprint,declared_document_count,"
                          "declared_evidence_count,supersedes_version_ref,created_by) "
                          "VALUES (%s,%s,'PROJECT',%s,3,'{}'::jsonb,'TYPE','INTERNAL',"
                          "%s,%s,1,0,%s,%s)",
                          (uuid.uuid4(), root, project, b"c" * 32, b"s" * 32,
                           revised, actor)))
        prior.rejects("ReferenceSolution revise result Owner is not installed",
                      lambda: db.execute(statement, values))
        prior.rejects("ReferenceSolution history cannot be truncated",
                      lambda: db.execute("TRUNCATE plm.sol_reference_revise_results"))
        prior.rejects("ReferenceSolution history is immutable",
                      lambda: db.execute("UPDATE plm.sol_reference_solutions "
                                         "SET current_version_ref=%s WHERE reference_solution_id=%s",
                                         (revised, root)))
        db.execute("ALTER TABLE plm.sol_reference_revise_results "
                   "DISABLE TRIGGER trg_sol_reference_revise_results__owner")
        try:
            prior.rejects("fk_sol_reference_revise_results__version",
                          lambda: db.execute(statement, (uuid.uuid4(), root, 2, first,
                                                         b"c" * 32, b"s" * 32)))
            prior.rejects("fk_sol_reference_revise_results__supersedes",
                          lambda: db.execute(statement, (revised, root, 2, uuid.uuid4(),
                                                         b"c" * 32, b"s" * 32)))
            prior.rejects("ck_sol_reference_revise_results__number",
                          lambda: db.execute(statement, (revised, root, 1, first,
                                                         b"c" * 32, b"s" * 32)))
            prior.rejects("ck_sol_reference_revise_results__content_fingerprint",
                          lambda: db.execute(statement, (revised, root, 2, first,
                                                         b"short", b"s" * 32)))
            db.execute(statement, values)
            prior.rejects("pk_sol_reference_revise_results",
                          lambda: db.execute(statement, values))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "Reference revise result history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("Reference revise result history was dropped")
            db.execute("DELETE FROM plm.sol_reference_revise_results "
                       "WHERE reference_version_id=%s", (revised,))
        finally:
            db.execute("ALTER TABLE plm.sol_reference_revise_results "
                       "ENABLE TRIGGER trg_sol_reference_revise_results__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    print("SOL_01_A06_REFERENCE_REVISE_RESULT_SCHEMA_PASS: empty/existing upgrade, "
          "down/re-up, drift, closed result/root pointer, FK/check/duplicate/history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol01-revise-pg-"))
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
                and scratch.name.startswith("plm-sol01-revise-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
