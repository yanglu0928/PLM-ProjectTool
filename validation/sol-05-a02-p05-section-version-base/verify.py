"""Disposable Win11 PostgreSQL proof for current SectionVersion parent/sequence."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import psycopg
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.solution.infrastructure.section_version_base import (
    SqlAlchemyCurrentSectionVersionBase,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_schema_fixture", ROOT / "validation/sol-01-a03-p02-section-version-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, "head")
    command.check(cfg)
    project, other_project = uuid.uuid4(), uuid.uuid4()
    outline, other_outline = uuid.uuid4(), uuid.uuid4()
    section, other_section = uuid.uuid4(), uuid.uuid4()
    version, version_two, broken_version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Section base actor','section base actor') RETURNING user_id"
        ).fetchone()[0]
        for project_id, code in ((project, "SOLBASE1"), (other_project, "SOLBASE2")):
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,"
                "name,created_by) VALUES (%s,%s,%s,%s,%s)",
                (project_id, code, code.lower(), code, actor))
        try:
            db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_id,project_id,"
                "version_no,title,content_artifact_ref,content_fingerprint,"
                "assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,1,'Closed',%s,%s,'[]','[]',0,0,%s)",
                (section, project, uuid.uuid4(), b"v" * 32, actor))
        except psycopg.errors.RaiseException as error:
            assert "SolutionSectionVersion Owner is not installed" in str(error), str(error)
        else:
            raise AssertionError("0138 SectionVersion write guard unexpectedly opened")
        # Disposable fixture rows are inserted without invoking write Owners;
        # the production guards remain unchanged after this connection closes.
        db.execute("SET session_replication_role='replica'")
        try:
            for outline_id, project_id in ((outline, project), (other_outline, other_project)):
                db.execute(
                    "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Parent',%s)", (outline_id, project_id, actor))
            for section_id, outline_id, project_id in (
                (section, outline, project), (other_section, other_outline, other_project)
            ):
                db.execute(
                    "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                    "project_id,section_key,created_by) VALUES (%s,%s,%s,'base',%s)",
                    (section_id, outline_id, project_id, actor))
            engine = create_engine(url)
            try:
                port_adapter = SqlAlchemyCurrentSectionVersionBase()

                def current(project_id: uuid.UUID, section_id: uuid.UUID):
                    with Session(engine) as session, session.begin():
                        return port_adapter.current(SimpleNamespace(session=session),
                                                    project_id=project_id,
                                                    section_id=section_id)

                first = current(project, section)
                assert (first.solution_outline_id, first.next_version_no,
                        first.supersedes_version_id) == (outline, 1, None)
                assert current(project, other_section) is None
                assert current(other_project, section) is None
                db.execute(
                    "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                    "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,created_by) "
                    "VALUES (%s,%s,%s,1,'First',%s,%s,'[]','[]',0,0,%s)",
                    (version, section, project, uuid.uuid4(), b"v" * 32, actor))
                second = current(project, section)
                assert (second.next_version_no, second.supersedes_version_id) == (2, version)
                db.execute(
                    "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                    "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,supersedes_version_ref,created_by) "
                    "VALUES (%s,%s,%s,2,'Second',%s,%s,'[]','[]',0,0,%s,%s)",
                    (version_two, section, project, uuid.uuid4(), b"w" * 32, version, actor))
                third = current(project, section)
                assert (third.next_version_no, third.supersedes_version_id) == (3, version_two)
                db.execute("UPDATE plm.sol_outlines SET outline_state='ARCHIVED' "
                           "WHERE solution_outline_id=%s", (outline,))
                assert current(project, section) is None
                db.execute("UPDATE plm.sol_outlines SET outline_state='ACTIVE' "
                           "WHERE solution_outline_id=%s", (outline,))
                db.execute("UPDATE plm.sol_sections SET section_state='ARCHIVED' "
                           "WHERE solution_section_id=%s", (section,))
                assert current(project, section) is None
                db.execute("UPDATE plm.sol_sections SET section_state='ACTIVE' "
                           "WHERE solution_section_id=%s", (section,))
                assert current(project, section).next_version_no == 3
                db.execute(
                    "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                    "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,supersedes_version_ref,created_by) "
                    "VALUES (%s,%s,%s,3,'Broken',%s,%s,'[]','[]',0,0,%s,%s)",
                    (broken_version, section, project, uuid.uuid4(), b"x" * 32, version, actor))
                assert current(project, section) is None
            finally:
                engine.dispose()
        finally:
            db.execute("SET session_replication_role='origin'")
    print("SOL_05_A02_P05_SECTION_VERSION_BASE_PG_PASS: closed write guard, first/next, "
          "project isolation, archival, predecessor gap rejection")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-section-base-pg-"))
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
                and scratch.name.startswith("plm-sol-section-base-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
