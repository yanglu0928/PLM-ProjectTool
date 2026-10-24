"""Disposable Win11 PG18 proof for closed SectionVersion first-response 0159."""

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
PREVIOUS = "20261009_0158"
TABLE = "plm.sol_section_version_create_results"


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
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
        rejects("create result history cannot be truncated",
                lambda: db.execute(f"TRUNCATE {TABLE}"))
    command.downgrade(cfg, PREVIOUS)

    project, outline, section, version = (uuid.uuid4() for _ in range(4))
    artifact = uuid.uuid4()
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Section result actor','section result actor') RETURNING user_id"
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,"
            "name,created_by) VALUES (%s,'SOLRSLT','solrslt','Section result',%s)",
            (project, actor))
        # Existing project + Section history before 0159. The disposable
        # fixture bypasses later Owner closure only while seeding identities.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Historical outline',%s)", (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'historical',%s)",
                (section, outline, project, actor))
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT solution_outline_id FROM plm.sol_sections "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == outline
        rejects("create result Owner is not installed", lambda: db.execute(
            f"INSERT INTO {TABLE}(solution_section_version_id,solution_section_id,"
            "project_id,version_no,title,content_artifact_ref,content_fingerprint,"
            "assumptions,exclusions,declared_requirement_count,declared_evidence_count,"
            "created_by,created_at) VALUES (%s,%s,%s,1,'Closed',%s,%s,'[]','[]',0,0,%s,now())",
            (version, section, project, artifact, b"f" * 32, actor)))
        rejects("create result history cannot be truncated",
                lambda: db.execute(f"TRUNCATE {TABLE}"))
        rejects("SolutionSectionVersion Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.sol_section_versions(solution_section_id,project_id,"
            "version_no,title,content_artifact_ref,content_fingerprint,"
            "assumptions,exclusions,declared_requirement_count,declared_evidence_count,"
            "created_by) VALUES (%s,%s,1,'Closed',%s,%s,'[]','[]',0,0,%s)",
            (section, project, artifact, b"f" * 32, actor)))

        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            created_at = db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,%s,1,'Historical',%s,%s,'[]','[]',0,0,%s) "
                "RETURNING created_at",
                (version, section, project, artifact, b"f" * 32, actor)).fetchone()[0]

        db.execute("ALTER TABLE plm.sol_section_version_create_results "
                   "DISABLE TRIGGER trg_sol_section_version_create_results__owner")
        try:
            insert = (
                f"INSERT INTO {TABLE}(solution_section_version_id,solution_section_id,"
                "project_id,version_no,title,content_artifact_ref,content_fingerprint,"
                "assumptions,exclusions,declared_requirement_count,declared_evidence_count,"
                "created_by,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,'[]'::jsonb,0,0,%s,%s)"
            )
            args = (version, section, project, 1, "Historical", artifact,
                    b"f" * 32, actor, created_at)
            rejects("ck_sol_section_version_results__number", lambda: db.execute(
                insert, (version, section, project, 0, "Historical", artifact,
                         b"f" * 32, actor, created_at)))
            rejects("ck_sol_section_version_results__title", lambda: db.execute(
                insert, (version, section, project, 1, " Historical", artifact,
                         b"f" * 32, actor, created_at)))
            rejects("ck_sol_section_version_results__fingerprint", lambda: db.execute(
                insert, (version, section, project, 1, "Historical", artifact,
                         b"bad", actor, created_at)))
            rejects("ck_sol_section_version_results__content_xor", lambda: db.execute(
                insert, (version, section, project, 1, "Historical", None,
                         b"f" * 32, actor, created_at)))
            rejects("ck_sol_section_version_results__declarations", lambda: db.execute(
                insert.replace("'[]'::jsonb,'[]'::jsonb",
                               "'{}'::jsonb,'[]'::jsonb"), args))
            rejects("ck_sol_section_version_results__counts", lambda: db.execute(
                insert.replace("'[]'::jsonb,0,0,%s,%s",
                               "'[]'::jsonb,-1,0,%s,%s"), args))
            rejects("fk_sol_section_version_results__version", lambda: db.execute(
                insert, (version, uuid.uuid4(), project, 1, "Historical", artifact,
                         b"f" * 32, actor, created_at)))
            db.execute(insert, args)
            assert db.execute(f"SELECT content_fingerprint FROM {TABLE} "
                              "WHERE solution_section_version_id=%s", (version,)).fetchone()[0] == b"f" * 32
            rejects("SectionVersion create result history prevents downgrade",
                    lambda: command.downgrade(cfg, PREVIOUS))
            db.execute("ALTER TABLE plm.sol_section_version_create_results "
                       "ENABLE TRIGGER trg_sol_section_version_create_results__owner")
            rejects("create result Owner is not installed", lambda: db.execute(
                f"UPDATE {TABLE} SET title='Changed' WHERE solution_section_version_id=%s",
                (version,)))
            rejects("create result Owner is not installed", lambda: db.execute(
                f"DELETE FROM {TABLE} WHERE solution_section_version_id=%s", (version,)))
            db.execute("ALTER TABLE plm.sol_section_version_create_results "
                       "DISABLE TRIGGER trg_sol_section_version_create_results__owner")
            db.execute(f"DELETE FROM {TABLE} WHERE solution_section_version_id=%s", (version,))
        finally:
            db.execute("ALTER TABLE plm.sol_section_version_create_results "
                       "ENABLE TRIGGER trg_sol_section_version_create_results__owner")
        # Disposable synthetic version is removed under the isolated fixture
        # role; no production/history cleanup is performed by this script.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("DELETE FROM plm.sol_section_versions "
                       "WHERE solution_section_version_id=%s", (version,))
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT solution_outline_id FROM plm.sol_sections "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == outline
        assert db.execute("SELECT to_regclass('plm.sol_section_version_create_results')").fetchone()[0] is None
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_05_A02_P09_SECTION_VERSION_FIRST_RESULT_SCHEMA_PASS: empty/existing "
          "upgrade, empty downgrade/re-upgrade, constraints, DML guards, nonempty refusal, drift")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-section-result-pg-"))
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
                and scratch.name.startswith("plm-sol-section-result-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
