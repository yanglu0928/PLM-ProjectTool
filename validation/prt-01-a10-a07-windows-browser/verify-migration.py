"""Isolated PostgreSQL 18 upgrade, legacy-row and downgrade proof for 0135."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261008_0134"
CURRENT = "20261008_0135"


def main() -> None:
    database = "prt01a10a07schema_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        with connect(database) as db:
            actor = seed_user(db, "Prototype 0135 migration actor", "NONE", b"v" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRT0135','prt0135','Synthetic migration project',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
            root, template, template_version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            version, result = uuid.uuid4(), uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Synthetic root',%s)", (root, project, actor))
                db.execute(
                    "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,"
                    "current_template_version_ref,created_by) VALUES "
                    "(%s,'PROJECT',%s,'Synthetic template',%s,%s)",
                    (template, project, template_version, actor))
                db.execute(
                    "INSERT INTO plm.prt_template_versions(prototype_template_version_id,"
                    "prototype_template_id,scope,project_id,version_no,content_fingerprint,"
                    "layout_contract,component_contract,applicable_terminals,declared_artifact_count,created_by) "
                    "VALUES (%s,%s,'PROJECT',%s,1,%s,'{}','{}',ARRAY['DESKTOP_WEB'],0,%s)",
                    (template_version, template, project, b"t" * 32, actor))
                db.execute(
                    "INSERT INTO plm.prt_prototype_versions(prototype_version_id,prototype_id,"
                    "project_id,version_no,template_ref,template_version_ref,coverage_summary,"
                    "content_fingerprint,declared_artifact_count,declared_requirement_count,"
                    "declared_interaction_count,created_by) VALUES "
                    "(%s,%s,%s,1,%s,%s,'{}',%s,1,1,1,%s)",
                    (version, root, project, template, template_version, b"f" * 32, actor))
                db.execute(
                    "INSERT INTO plm.prt_version_create_results(result_id,prototype_version_id,"
                    "prototype_id,project_id,version_no,content_fingerprint,"
                    "declared_artifact_count,declared_requirement_count,declared_interaction_count) "
                    "VALUES (%s,%s,%s,%s,1,%s,1,1,1)",
                    (result, version, root, project, b"f" * 32))
        command.upgrade(cfg, CURRENT)
        with connect(database) as db:
            assert db.execute(
                "SELECT prototype_lock_version FROM plm.prt_version_create_results "
                "WHERE result_id=%s", (result,)).fetchone() == (None,)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, CURRENT)
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.prt_version_create_results SET prototype_lock_version=1 "
                    "WHERE result_id=%s", (result,))
        try:
            command.downgrade(cfg, PREVIOUS)
        except RuntimeError as error:
            assert "history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("non-null immutable result must prevent downgrade")
        print("PRT_01_A10_A07_SCHEMA0135_MIGRATION_PASS")
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
