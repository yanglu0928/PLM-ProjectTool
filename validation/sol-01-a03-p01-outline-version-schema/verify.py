"""Disposable PostgreSQL 18 proof for closed SolutionOutlineVersion Schema0137."""

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
PREVIOUS = "20261008_0136"


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
            "VALUES ('Solution Version Actor','solution version actor') RETURNING user_id"
        ).fetchone()[0]
        project_one = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOLV01','solv01','Solution version one',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        project_two = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('SOLV02','solv02','Solution version two',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)

    outline_one, outline_two = uuid.uuid4(), uuid.uuid4()
    section_one, section_two = uuid.uuid4(), uuid.uuid4()
    version = uuid.uuid4()
    requirement, requirement_version = uuid.uuid4(), uuid.uuid4()
    other_requirement, other_requirement_version = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rejects("SolutionOutlineVersion Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_outline_versions(solution_outline_id,project_id,version_no,"
            "content_fingerprint,missing_declarations,conflict_declarations,"
            "declared_section_count,declared_requirement_count,created_by) "
            "VALUES (%s,%s,1,%s,'[]'::jsonb,'[]'::jsonb,0,0,%s)",
            (outline_one, project_one, b"v" * 32, actor)))
        rejects("SolutionOutlineVersion history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.sol_outline_sections"))

        # Synthetic upstream Requirement records only; bypass its unrelated Owner
        # while retaining ordinary constraints for all Solution negative cases.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            for req_id, version_id, project_id, code in (
                (requirement, requirement_version, project_one, "SOLV-REQ-1"),
                (other_requirement, other_requirement_version, project_two, "SOLV-REQ-2"),
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

        for table in ("sol_outlines", "sol_sections", "sol_outline_versions",
                      "sol_outline_sections", "sol_outline_requirement_refs"):
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER trg_{table}__owner")
        try:
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Outline one',%s),(%s,%s,'Outline two',%s)",
                (outline_one, project_one, actor, outline_two, project_one, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,project_id,solution_outline_id,"
                "section_key,created_by) VALUES (%s,%s,%s,'intro',%s),(%s,%s,%s,'scope',%s)",
                (section_one, project_one, outline_one, actor,
                 section_two, project_one, outline_two, actor))
            db.execute(
                "INSERT INTO plm.sol_outline_versions(solution_outline_version_id,solution_outline_id,"
                "project_id,version_no,content_fingerprint,missing_declarations,"
                "conflict_declarations,declared_section_count,declared_requirement_count,created_by) "
                "VALUES (%s,%s,%s,1,%s,'[]'::jsonb,'[]'::jsonb,1,1,%s)",
                (version, outline_one, project_one, b"v" * 32, actor))
            rejects("ck_sol_outline_versions__declarations", lambda: db.execute(
                "INSERT INTO plm.sol_outline_versions(solution_outline_id,project_id,version_no,"
                "content_fingerprint,missing_declarations,conflict_declarations,"
                "declared_section_count,declared_requirement_count,created_by) "
                "VALUES (%s,%s,2,%s,'{}'::jsonb,'[]'::jsonb,1,1,%s)",
                (outline_one, project_one, b"v" * 32, actor)))
            rejects("ck_sol_outline_versions__fingerprint", lambda: db.execute(
                "INSERT INTO plm.sol_outline_versions(solution_outline_id,project_id,version_no,"
                "content_fingerprint,missing_declarations,conflict_declarations,"
                "declared_section_count,declared_requirement_count,created_by) "
                "VALUES (%s,%s,2,%s,'[]'::jsonb,'[]'::jsonb,1,1,%s)",
                (outline_one, project_one, b"bad", actor)))

            db.execute(
                "INSERT INTO plm.sol_outline_sections(solution_outline_version_id,solution_outline_id,"
                "project_id,solution_section_id,ordinal) VALUES (%s,%s,%s,%s,1)",
                (version, outline_one, project_one, section_one))
            rejects("fk_sol_outline_sections__section", lambda: db.execute(
                "INSERT INTO plm.sol_outline_sections(solution_outline_version_id,solution_outline_id,"
                "project_id,solution_section_id,ordinal) VALUES (%s,%s,%s,%s,2)",
                (version, outline_one, project_one, section_two)))
            rejects("uq_sol_outline_sections__version_ordinal", lambda: db.execute(
                "INSERT INTO plm.sol_outline_sections(solution_outline_version_id,solution_outline_id,"
                "project_id,solution_section_id,ordinal) VALUES (%s,%s,%s,%s,1)",
                (version, outline_one, project_one, section_two)))
            db.execute(
                "INSERT INTO plm.sol_outline_requirement_refs(solution_outline_version_id,"
                "solution_outline_id,project_id,requirement_id,requirement_version_id,ordinal) "
                "VALUES (%s,%s,%s,%s,%s,1)",
                (version, outline_one, project_one, requirement, requirement_version))
            rejects("fk_sol_outline_requirements__requirement", lambda: db.execute(
                "INSERT INTO plm.sol_outline_requirement_refs(solution_outline_version_id,"
                "solution_outline_id,project_id,requirement_id,requirement_version_id,ordinal) "
                "VALUES (%s,%s,%s,%s,%s,2)",
                (version, outline_one, project_one, other_requirement, other_requirement_version)))
            rejects("fk_sol_outlines__approved_version", lambda: db.execute(
                "UPDATE plm.sol_outlines SET current_approved_version_ref=%s "
                "WHERE solution_outline_id=%s", (version, outline_two)))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "SolutionOutlineVersion history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("SolutionOutlineVersion history was dropped")

            db.execute("DELETE FROM plm.sol_outline_requirement_refs")
            db.execute("DELETE FROM plm.sol_outline_sections")
            db.execute("DELETE FROM plm.sol_outline_versions")
            db.execute("DELETE FROM plm.sol_sections")
            db.execute("DELETE FROM plm.sol_outlines")
        finally:
            for table in reversed(("sol_outlines", "sol_sections", "sol_outline_versions",
                                   "sol_outline_sections", "sol_outline_requirement_refs")):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER trg_{table}__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_01_A03_P01_OUTLINE_VERSION_SCHEMA_PASS: empty/existing upgrade, "
          "downgrade, drift, fixed same-project refs, order and history guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-version-pg-"))
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
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-version-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
