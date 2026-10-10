"""Windows 11/PostgreSQL 18 proof for PrototypeVersion Schema0130."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261008_0129"


def expect_database(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def main() -> None:
    database = "prt01a05a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        with connect(database) as db:
            actor = seed_user(db, "PrototypeVersion schema actor", "NONE", b"v" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTV01','prtv01','Version schema project',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
        command.upgrade(cfg, "head"); command.check(cfg)
        with connect(database) as db:
            assert db.execute("SELECT name FROM plm.prj_projects WHERE project_id=%s", (project,)).fetchone()[0] == "Version schema project"
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head"); command.check(cfg)

        prototype_id, template_id = uuid.uuid4(), uuid.uuid4()
        template_version_id, prototype_version_id = uuid.uuid4(), uuid.uuid4()
        with connect(database) as db:
            expect_database(
                "PrototypeVersion Owner is not installed",
                lambda: db.execute(
                    "INSERT INTO plm.prt_prototype_versions(prototype_version_id,prototype_id,"
                    "project_id,version_no,template_ref,template_version_ref,coverage_summary,"
                    "content_fingerprint,declared_artifact_count,declared_requirement_count,"
                    "declared_interaction_count,created_by) VALUES (%s,%s,%s,1,%s,%s,'{}',%s,1,1,1,%s)",
                    (prototype_version_id, prototype_id, project, template_id,
                     template_version_id, b"f" * 32, actor),
                ),
            )
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Schema prototype',%s)", (prototype_id, project, actor),
                )
                db.execute(
                    "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,"
                    "current_template_version_ref,created_by) VALUES (%s,'PROJECT',%s,'Schema template',%s,%s)",
                    (template_id, project, template_version_id, actor),
                )
                db.execute(
                    "INSERT INTO plm.prt_template_versions(prototype_template_version_id,"
                    "prototype_template_id,scope,project_id,version_no,content_fingerprint,"
                    "layout_contract,component_contract,applicable_terminals,declared_artifact_count,created_by) "
                    "VALUES (%s,%s,'PROJECT',%s,1,%s,'{}','{}',ARRAY['DESKTOP_WEB'],0,%s)",
                    (template_version_id, template_id, project, b"t" * 32, actor),
                )

            def invalid_counts() -> None:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.prt_prototype_versions(prototype_version_id,prototype_id,"
                        "project_id,version_no,template_ref,template_version_ref,coverage_summary,"
                        "content_fingerprint,declared_artifact_count,declared_requirement_count,"
                        "declared_interaction_count,created_by) VALUES (%s,%s,%s,1,%s,%s,'{}',%s,0,1,1,%s)",
                        (uuid.uuid4(), prototype_id, project, template_id,
                         template_version_id, b"f" * 32, actor),
                    )
            expect_database("ck_prt_versions__counts", invalid_counts)

            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.prt_prototype_versions(prototype_version_id,prototype_id,"
                    "project_id,version_no,template_ref,template_version_ref,coverage_summary,"
                    "content_fingerprint,declared_artifact_count,declared_requirement_count,"
                    "declared_interaction_count,created_by) VALUES (%s,%s,%s,1,%s,%s,'{}',%s,1,1,1,%s)",
                    (prototype_version_id, prototype_id, project, template_id,
                     template_version_id, b"f" * 32, actor),
                )

            def invalid_interaction() -> None:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.prt_interaction_specs(prototype_version_id,prototype_id,"
                        "project_id,schema_version,specification,content_fingerprint) "
                        "VALUES (%s,%s,%s,1,'[]',%s)",
                        (prototype_version_id, prototype_id, project, b"i" * 32),
                    )
            expect_database("ck_prt_interactions__specification", invalid_interaction)
            expect_database(
                "PrototypeVersion history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.prt_interaction_specs"),
            )
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "PrototypeVersion history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0130 accepted PrototypeVersion history downgrade")
        print(
            "PRT_01_A05_A02_PROTOTYPE_VERSION_SCHEMA_PASS: existing-data upgrade, "
            "empty downgrade/re-upgrade, drift, closed Owner, composite parent/template, "
            "count/JSON constraints, immutable truncation and history refusal verified "
            "on PostgreSQL 18"
        )
    finally:
        with connect("postgres") as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (database,))
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
