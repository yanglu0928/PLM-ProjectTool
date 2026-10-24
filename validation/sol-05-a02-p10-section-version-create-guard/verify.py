"""Disposable Win11 PG18 proof for SectionVersion INSERT-only 0160 guard."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_schema_fixture", ROOT / "validation/sol-01-a03-p02-section-version-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
PREVIOUS = "20261009_0159"
TABLES = (
    "sol_section_versions", "sol_section_requirement_refs",
    "sol_section_evidence_refs", "sol_section_version_create_results",
)


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
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)

    project, outline, section, document, document_version = (uuid.uuid4() for _ in range(5))
    version, second_version, incomplete_version = (uuid.uuid4() for _ in range(3))
    requirement, requirement_version, evidence_id = (uuid.uuid4() for _ in range(3))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Section guard actor','section guard actor') RETURNING user_id"
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,"
            "name,created_by) VALUES (%s,'SOLGUARD','solguard','Section guard',%s)",
            (project, actor))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Guard outline',%s)", (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'guard',%s)",
                (section, outline, project, actor))
            db.execute(
                "INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,"
                "title,original_display_name,created_by) "
                "VALUES (%s,'PROJECT',%s,'PROJECT_RECORD','Guard source','guard.txt',%s)",
                (document, project, actor))
            db.execute(
                "INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,"
                "project_id,version_no,file_object_id,content_sha256,size_bytes,detected_mime,created_by) "
                "VALUES (%s,%s,'PROJECT',%s,1,%s,%s,1,'text/plain',%s)",
                (document_version, document, project, uuid.uuid4(), b"d" * 32, actor))
            db.execute(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
                "requirement_code_normalized,created_by) VALUES (%s,%s,'SOLGUARD-REQ',"
                "'SOLGUARD-REQ',%s)", (requirement, project, actor))
            db.execute(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,"
                "project_id,version_no,statement,rationale,domain_name,priority,risk,"
                "requirement_classification,content_fingerprint,declared_source_count,"
                "declared_acceptance_count,declared_capability_count,declared_assumption_count,"
                "declared_exclusion_count,declared_dependency_count,declared_ai_task_count,created_by) "
                "VALUES (%s,%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                (requirement_version, requirement, project, b"r" * 32, actor))
            db.execute(
                "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,"
                "document_version_id,locator_type,locator_payload,content_fingerprint,"
                "display_label,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',"
                "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Evidence',%s)",
                (evidence_id, project, document, document_version, b"e" * 32, actor))
            db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,%s,1,'Unaudited',%s,%s,'[]','[]',0,0,%s)",
                (incomplete_version, section, project, uuid.uuid4(), b"u" * 32, actor))
    rejects("pre-existing SectionVersion requires audited Owner migration",
            lambda: command.upgrade(cfg, "head"))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("DELETE FROM plm.sol_section_versions "
                       "WHERE solution_section_version_id=%s", (incomplete_version,))
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_sections WHERE solution_section_id=%s",
                          (section,)).fetchone()[0] == 1
        for table in TABLES:
            rejects("cannot be truncated" if table != "sol_section_versions" else "cannot truncate",
                    lambda t=table: db.execute(f"TRUNCATE plm.{t}"))
        insert = (
            "INSERT INTO plm.sol_section_versions(solution_section_version_id,solution_section_id,"
            "project_id,version_no,title,content_document_version_ref,content_artifact_ref,"
            "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
            "declared_evidence_count,supersedes_version_ref,created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,'[]'::jsonb,%s,%s,%s,%s) "
            "RETURNING created_at"
        )
        result = (
            "INSERT INTO plm.sol_section_version_create_results(solution_section_version_id,"
            "solution_section_id,project_id,version_no,title,content_document_version_ref,"
            "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
            "declared_evidence_count,supersedes_version_ref,created_by,created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,'[]'::jsonb,%s,%s,%s,%s,%s)"
        )
        def row_args(vid, number, title="Draft", doc=document_version, artifact=None,
                     requirements=0, evidence=0, predecessor=None):
            return (vid, section, project, number, title, doc, artifact,
                    b"f" * 32, requirements, evidence, predecessor, actor)
        def result_args(vid, number, created_at, title="Draft", predecessor=None,
                        requirements=0, evidence=0):
            return (vid, section, project, number, title, document_version,
                    b"f" * 32, requirements, evidence, predecessor, actor, created_at)

        rejects("initial state is invalid", lambda: db.execute(
            insert, row_args(uuid.uuid4(), 1, doc=None, artifact=uuid.uuid4())))
        rejects("chain is invalid", lambda: db.execute(
            insert, row_args(uuid.uuid4(), 2)))
        rejects("create set is incomplete", lambda: db.execute(
            insert, row_args(incomplete_version, 1)))
        def missing_references() -> None:
            with db.transaction():
                stamp = db.execute(insert, row_args(incomplete_version, 1,
                                        requirements=1, evidence=1)).fetchone()[0]
                db.execute(result, result_args(incomplete_version, 1, stamp,
                                              requirements=1, evidence=1))
        rejects("create set is incomplete", missing_references)
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions").fetchone()[0] == 0
        with db.transaction():
            created_at = db.execute(insert, row_args(version, 1)).fetchone()[0]
            def mismatched_result() -> None:
                with db.transaction():
                    db.execute(result, result_args(version, 1, created_at, title="Wrong"))
            rejects("result does not match version", mismatched_result)
            db.execute(result, result_args(version, 1, created_at))
        assert db.execute("SELECT count(*) FROM plm.sol_section_versions").fetchone()[0] == 1
        rejects("history is immutable", lambda: db.execute(
            "UPDATE plm.sol_section_versions SET title='Changed' WHERE solution_section_version_id=%s",
            (version,)))
        rejects("history is immutable", lambda: db.execute(
            "DELETE FROM plm.sol_section_versions WHERE solution_section_version_id=%s",
            (version,)))
        rejects("create result is immutable", lambda: db.execute(
            "UPDATE plm.sol_section_version_create_results SET title='Changed' "
            "WHERE solution_section_version_id=%s", (version,)))
        rejects("SectionVersion history prevents Owner guard downgrade",
                lambda: command.downgrade(cfg, PREVIOUS))
        with db.transaction():
            created_at = db.execute(
                insert, row_args(second_version, 2, requirements=1, evidence=1,
                                 predecessor=version)).fetchone()[0]
            def bad_ordinal() -> None:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.sol_section_requirement_refs("
                        "solution_section_version_id,solution_section_id,project_id,"
                        "requirement_id,requirement_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,2)",
                        (second_version, section, project, requirement, requirement_version))
            rejects("RequirementRef is invalid", bad_ordinal)
            db.execute(
                "INSERT INTO plm.sol_section_requirement_refs("
                "solution_section_version_id,solution_section_id,project_id,"
                "requirement_id,requirement_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,1)",
                (second_version, section, project, requirement, requirement_version))
            db.execute(
                "INSERT INTO plm.sol_section_evidence_refs("
                "solution_section_version_id,solution_section_id,project_id,evidence_id,ordinal) "
                "VALUES (%s,%s,%s,%s,1)",
                (second_version, section, project, evidence_id))
            db.execute(result, result_args(second_version, 2, created_at,
                                           predecessor=version, requirements=1, evidence=1))
        assert db.execute("SELECT version_no FROM plm.sol_section_versions "
                          "WHERE solution_section_version_id=%s", (second_version,)).fetchone()[0] == 2
        for table in ("sol_section_requirement_refs", "sol_section_evidence_refs"):
            rejects("history is immutable", lambda t=table: db.execute(
                f"UPDATE plm.{t} SET ordinal=ordinal WHERE solution_section_version_id=%s",
                (second_version,)))
            rejects("history is immutable", lambda t=table: db.execute(
                f"DELETE FROM plm.{t} WHERE solution_section_version_id=%s",
                (second_version,)))
        rejects("create result is immutable", lambda: db.execute(
            "DELETE FROM plm.sol_section_version_create_results "
            "WHERE solution_section_version_id=%s", (second_version,)))
        # Synthetic rows are removed only inside the disposable PG fixture.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("DELETE FROM plm.sol_section_version_create_results")
            db.execute("DELETE FROM plm.sol_section_requirement_refs")
            db.execute("DELETE FROM plm.sol_section_evidence_refs")
            db.execute("DELETE FROM plm.sol_section_versions")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_05_A02_P10_SECTION_VERSION_CREATE_GUARD_PG_PASS: empty/existing upgrade, "
          "empty downgrade/re-upgrade, document-only insert, closure, immutable history, "
          "nonempty refusal, drift")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-section-guard-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(fixture.PG_SOURCE / name, install / name)
    shutil.copy2(fixture.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(fixture.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (fixture.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary = install / "bin"
    data = scratch / "data"
    port = fixture.free_port()
    started = False
    try:
        fixture.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                    "-A", "trust", "--no-locale", "-E", "UTF8")
        fixture.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l",
                    str(scratch / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}",
                    "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            fixture.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-section-guard-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
