"""Disposable PG proof of 0150 empty/v1 upgrade and legacy-v2 refusal."""

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
    "reference_revise_0149_fixture",
    ROOT / "validation/sol-01-a06-reference-revise-result-schema/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
helper = base.prior


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, "20261009_0149")
    command.upgrade(cfg, "20261009_0151")
    command.check(cfg)
    command.downgrade(cfg, "20261009_0149")
    command.upgrade(cfg, "20261009_0151")
    command.check(cfg)
    command.downgrade(cfg, "20261009_0149")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Reference Migration Actor','reference migration actor') "
            "RETURNING user_id").fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('SOL15','sol15','Reference migration',%s) "
            "RETURNING project_id", (actor,)).fetchone()[0]
        root, first, legacy = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with db.transaction():
            db.execute(
                "INSERT INTO plm.sol_reference_solutions"
                "(reference_solution_id,scope,project_id,name,current_version_ref,created_by) "
                "VALUES (%s,'PROJECT',%s,'Migration root',%s,%s)",
                (root, project, first, actor))
            db.execute(
                "INSERT INTO plm.sol_reference_versions"
                "(reference_version_id,reference_solution_id,scope,project_id,version_no,"
                "applicability,source_project_class,deidentification_class,"
                "content_fingerprint,source_fingerprint,declared_document_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,'PROJECT',%s,1,'{}'::jsonb,'PLM','INTERNAL',"
                "%s,%s,1,0,%s)",
                (first, root, project, b"c" * 32, b"s" * 32, actor))
    command.upgrade(cfg, "20261009_0151")
    command.check(cfg)
    command.downgrade(cfg, "20261009_0149")
    command.upgrade(cfg, "20261009_0151")
    command.check(cfg)
    command.downgrade(cfg, "20261009_0148")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute(
            "INSERT INTO plm.sol_reference_versions"
            "(reference_version_id,reference_solution_id,scope,project_id,version_no,"
            "applicability,source_project_class,deidentification_class,"
            "content_fingerprint,source_fingerprint,declared_document_count,"
            "declared_evidence_count,supersedes_version_ref,created_by) "
            "VALUES (%s,%s,'PROJECT',%s,2,'{}'::jsonb,'PLM','INTERNAL',"
            "%s,%s,1,0,%s,%s)",
            (legacy, root, project, b"c" * 32, b"s" * 32, first, actor))
    command.upgrade(cfg, "20261009_0149")
    try:
        command.upgrade(cfg, "20261009_0150")
    except Exception as error:
        assert "legacy Reference revisions require audited forward repair" in str(error), str(error)
    else:
        raise AssertionError("legacy revision without first result upgraded silently")
    print("SOL_01_A07_REFERENCE_REVISE_MIGRATION_PG_PASS: empty/v1 up/down/re-up, "
          "drift, legacy-v2 refusal")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol01-revise-owner-pg-"))
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
                and scratch.name.startswith("plm-sol01-revise-owner-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
