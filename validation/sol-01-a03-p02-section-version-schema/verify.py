"""Disposable PG18 proof for closed SolutionSectionVersion Schema0138."""

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
PREVIOUS = "20261008_0137"
TABLES = ("sol_outlines", "sol_sections", "sol_section_versions",
          "sol_section_requirement_refs", "sol_section_evidence_refs")


def run(*args: str, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(args, stdout=output, stderr=output, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Section Version Actor','section version actor') RETURNING user_id"
        ).fetchone()[0]
        project_one = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOLSEC1','solsec1','Section version one',%s) RETURNING project_id", (actor,)
        ).fetchone()[0]
        project_two = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOLSEC2','solsec2','Section version two',%s) RETURNING project_id", (actor,)
        ).fetchone()[0]
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)

    outline, section, other_section = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    other_outline = uuid.uuid4()
    version, other_version = uuid.uuid4(), uuid.uuid4()
    requirement, requirement_version = uuid.uuid4(), uuid.uuid4()
    other_requirement, other_requirement_version = uuid.uuid4(), uuid.uuid4()
    evidence = uuid.uuid4()
    missing_document = uuid.uuid4()
    document, document_version = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rejects("SolutionSectionVersion Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_section_versions(solution_section_id,project_id,version_no,title,"
            "content_artifact_ref,content_fingerprint,assumptions,exclusions,"
            "declared_requirement_count,declared_evidence_count,created_by) "
            "VALUES (%s,%s,1,'Title',%s,%s,'[]','[]',0,0,%s)",
            (section, project_one, uuid.uuid4(), b"v" * 32, actor)))
        rejects("SolutionSectionVersion history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.sol_section_evidence_refs"))

        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            for req_id, version_id, project_id, code in (
                (requirement, requirement_version, project_one, "SOLSEC-REQ-1"),
                (other_requirement, other_requirement_version, project_two, "SOLSEC-REQ-2"),
            ):
                db.execute(
                    "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
                    "requirement_code_normalized,created_by) VALUES (%s,%s,%s,%s,%s)",
                    (req_id, project_id, code, code, actor))
                db.execute(
                    "INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,"
                    "project_id,version_no,statement,rationale,domain_name,priority,risk,"
                    "requirement_classification,content_fingerprint,declared_source_count,"
                    "declared_acceptance_count,declared_capability_count,declared_assumption_count,"
                    "declared_exclusion_count,declared_dependency_count,declared_ai_task_count,created_by) "
                    "VALUES (%s,%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                    "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                    (version_id, req_id, project_id, b"r" * 32, actor))
            db.execute(
                "INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,"
                "title,original_display_name,created_by) "
                "VALUES (%s,'PROJECT',%s,'PROJECT_RECORD','Section source','section.txt',%s)",
                (document, project_one, actor))
            db.execute(
                "INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,"
                "project_id,version_no,file_object_id,content_sha256,size_bytes,detected_mime,created_by) "
                "VALUES (%s,%s,'PROJECT',%s,1,%s,%s,1,'text/plain',%s)",
                (document_version, document, project_one, uuid.uuid4(), b"d" * 32, actor))
            db.execute(
                "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,"
                "document_version_id,locator_type,locator_payload,content_fingerprint,"
                "display_label,created_by) "
                "VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',"
                "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Evidence',%s)",
                (evidence, project_one, document, document_version, b"e" * 32, actor))

        for table in TABLES:
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER trg_{table}__owner")
        try:
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Outline one',%s),(%s,%s,'Outline two',%s)",
                (outline, project_one, actor, other_outline, project_two, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,project_id,solution_outline_id,"
                "section_key,created_by) VALUES (%s,%s,%s,'intro',%s),(%s,%s,%s,'scope',%s)",
                (section, project_one, outline, actor,
                 other_section, project_two, other_outline, actor))
            insert = (
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,solution_section_id,"
                "project_id,version_no,title,content_document_version_ref,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,'[]'::jsonb,1,1,%s)"
            )
            db.execute(insert, (version, section, project_one, 1, "Intro", None,
                                uuid.uuid4(), b"v" * 32, actor))
            db.execute(insert, (other_version, other_section, project_two, 1, "Scope", None,
                                uuid.uuid4(), b"w" * 32, actor))
            db.execute(insert, (uuid.uuid4(), section, project_one, 2, "Intro revised",
                                document_version, None, b"x" * 32, actor))
            rejects("ck_sol_section_versions__content_xor", lambda: db.execute(
                insert, (uuid.uuid4(), section, project_one, 3, "Intro", None, None,
                         b"v" * 32, actor)))
            rejects("ck_sol_section_versions__content_xor", lambda: db.execute(
                insert, (uuid.uuid4(), section, project_one, 3, "Intro", missing_document,
                         uuid.uuid4(), b"v" * 32, actor)))
            rejects("fk_sol_section_versions__document", lambda: db.execute(
                insert, (uuid.uuid4(), section, project_one, 3, "Intro", missing_document,
                         None, b"v" * 32, actor)))
            rejects("ck_sol_section_versions__title", lambda: db.execute(
                insert, (uuid.uuid4(), section, project_one, 3, " Intro", None,
                         uuid.uuid4(), b"v" * 32, actor)))
            rejects("ck_sol_section_versions__fingerprint", lambda: db.execute(
                insert, (uuid.uuid4(), section, project_one, 3, "Intro", None,
                         uuid.uuid4(), b"bad", actor)))
            db.execute(
                "INSERT INTO plm.sol_section_requirement_refs(solution_section_version_id,"
                "solution_section_id,project_id,requirement_id,requirement_version_id,ordinal) "
                "VALUES (%s,%s,%s,%s,%s,1)",
                (version, section, project_one, requirement, requirement_version))
            rejects("fk_sol_section_requirements__requirement", lambda: db.execute(
                "INSERT INTO plm.sol_section_requirement_refs(solution_section_version_id,"
                "solution_section_id,project_id,requirement_id,requirement_version_id,ordinal) "
                "VALUES (%s,%s,%s,%s,%s,2)",
                (version, section, project_one, other_requirement, other_requirement_version)))
            db.execute(
                "INSERT INTO plm.sol_section_evidence_refs(solution_section_version_id,"
                "solution_section_id,project_id,evidence_id,ordinal) VALUES (%s,%s,%s,%s,1)",
                (version, section, project_one, evidence))
            rejects("uq_sol_section_evidence__version_evidence", lambda: db.execute(
                "INSERT INTO plm.sol_section_evidence_refs(solution_section_version_id,"
                "solution_section_id,project_id,evidence_id,ordinal) VALUES (%s,%s,%s,%s,2)",
                (version, section, project_one, evidence)))
            rejects("fk_sol_sections__approved_version", lambda: db.execute(
                "UPDATE plm.sol_sections SET current_approved_version_ref=%s "
                "WHERE solution_section_id=%s", (version, other_section)))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "SolutionSectionVersion history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("SolutionSectionVersion history was dropped")
            db.execute("DELETE FROM plm.sol_section_evidence_refs")
            db.execute("DELETE FROM plm.sol_section_requirement_refs")
            db.execute("DELETE FROM plm.sol_section_versions")
            db.execute("DELETE FROM plm.sol_sections")
            db.execute("DELETE FROM plm.sol_outlines")
        finally:
            for table in reversed(TABLES):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER trg_{table}__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_01_A03_P02_SECTION_VERSION_SCHEMA_PASS: existing/empty upgrade, downgrade, "
          "drift, fixed refs, content XOR, pointer and history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-section-pg-"))
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
    port = free_port()
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
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-section-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
