"""Windows 11/PostgreSQL 18 proof for PrototypeTemplate Schema0127."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py")
)
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261008_0126"


def expect_database(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def main() -> None:
    database = "prt01a04a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        with connect(database) as db:
            actor = seed_user(db, "Template schema actor", "NONE", b"t" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTT01','prtt01','Template schema project',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute(
                "SELECT name FROM plm.prj_projects WHERE project_id=%s", (project,)
            ).fetchone()[0] == "Template schema project"
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)

        template_id = uuid.uuid4()
        with connect(database) as db:
            expect_database(
                "PrototypeTemplate Owner is not installed",
                lambda: db.execute(
                    "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,created_by) "
                    "VALUES (%s,'PROJECT',%s,'Closed owner',%s)",
                    (template_id, project, actor),
                ),
            )

            def invalid_scope() -> None:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,created_by) "
                        "VALUES (%s,'GLOBAL',%s,'Invalid scope',%s)",
                        (uuid.uuid4(), project, actor),
                    )

            expect_database("ck_prt_templates__scope", invalid_scope)

            def valid_root() -> None:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.prt_templates(prototype_template_id,scope,project_id,name,created_by) "
                        "VALUES (%s,'PROJECT',%s,'Valid schema probe',%s)",
                        (template_id, project, actor),
                    )

            valid_root()

            def invalid_contract() -> None:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.prt_template_versions("
                        "prototype_template_version_id,prototype_template_id,scope,project_id,"
                        "version_no,content_fingerprint,layout_contract,component_contract,"
                        "applicable_terminals,created_by) VALUES (%s,%s,'PROJECT',%s,1,%s,"
                        "'[]'::jsonb,'{}'::jsonb,ARRAY['DESKTOP_WEB'],%s)",
                        (uuid.uuid4(), template_id, project, b"f" * 32, actor),
                    )

            expect_database("ck_prt_template_versions__layout", invalid_contract)

            version_id = uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.prt_template_versions("
                    "prototype_template_version_id,prototype_template_id,scope,project_id,"
                    "version_no,content_fingerprint,layout_contract,component_contract,"
                    "applicable_terminals,created_by) VALUES (%s,%s,'PROJECT',%s,1,%s,"
                    "'{\"schema\":1}'::jsonb,'{\"components\":[]}'::jsonb,"
                    "ARRAY['DESKTOP_WEB'],%s)",
                    (version_id, template_id, project, b"f" * 32, actor),
                )
                db.execute(
                    "UPDATE plm.prt_templates SET current_template_version_ref=%s "
                    "WHERE prototype_template_id=%s", (version_id, template_id),
                )
            assert db.execute(
                "SELECT count(*) FROM plm.prt_template_versions WHERE prototype_template_id=%s",
                (template_id,),
            ).fetchone()[0] == 1

            expect_database(
                "PrototypeTemplate history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.prt_template_command_results"),
            )

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "PrototypeTemplate history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0127 accepted Template history downgrade")
        print(
            "PRT_01_A04_A02_TEMPLATE_SCHEMA_PASS: existing-data upgrade, empty "
            "downgrade/re-upgrade, drift, closed Owner, scope/contract constraints, "
            "immutable truncation and history refusal verified on PostgreSQL 18"
        )
    finally:
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )


if __name__ == "__main__":
    main()
