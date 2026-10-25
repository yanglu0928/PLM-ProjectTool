"""Isolated PostgreSQL 18 migration proof for PlanVersion Review state guard 0190."""

from __future__ import annotations

import argparse
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, USER = "127.0.0.1", "poc_admin"
PREVIOUS = "20261026_0189"


def main(port: int) -> None:
    def connect(name: str) -> psycopg.Connection:
        return psycopg.connect(host=HOST, port=port, user=USER, dbname=name,
                               autocommit=True, connect_timeout=5)

    def config(name: str):
        url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                         port=port, database=name)
        return create_migration_config(url)

    suffix = uuid.uuid4().hex[:10]
    names = [f"plnrev0190_{suffix}_{part}" for part in ("empty",)]
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty = names[0]
            empty_config = config(empty)
            command.upgrade(empty_config, PREVIOUS)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            with connect(empty) as db:
                assert db.execute(
                    "SELECT to_regclass('plm.pln_plan_version_review_state_results')"
                ).fetchone()[0] == "plm.pln_plan_version_review_state_results"
                trigger_rows = db.execute(
                    "SELECT tgname FROM pg_trigger WHERE tgrelid='plm.pln_plan_versions'::regclass "
                    "AND NOT tgisinternal"
                ).fetchall()
                trigger_names = {row[0] for row in trigger_rows}
                assert {"trg_pln_plan_versions__owner",
                        "trg_pln_plan_versions__review_update",
                        "trg_pln_plan_versions__review_closure"} <= trigger_names
                assert db.execute(
                    "SELECT count(*) FROM plm.pln_plan_version_review_state_results"
                ).fetchone()[0] == 0
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES (%s,%s) RETURNING user_id",
                    ("Synthetic Plan Review Guard", "synthetic plan review guard " + suffix),
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES (%s,%s,%s,%s) RETURNING project_id",
                    ("PR0190" + suffix[:6], "pr0190" + suffix[:6], "Synthetic Plan Review Guard", actor),
                ).fetchone()[0]
                plan = uuid.uuid4()
                plan_name = "Synthetic guard plan"
                with db.transaction():
                    created_at = db.execute(
                        "INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) "
                        "VALUES (%s,%s,%s,%s) RETURNING created_at",
                        (plan, project, plan_name, actor),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                        "VALUES (%s,%s,%s,%s)", (plan, project, plan_name, created_at),
                    )
                version = db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                    "VALUES (%s,%s,1,%s) RETURNING plan_version_id",
                    (plan, project, actor),
                ).fetchone()[0]

                def reject(statement: str, params: tuple = (), message: str | None = None) -> None:
                    try:
                        with db.transaction():
                            db.execute(statement, params)
                    except psycopg.Error as exc:
                        assert exc.sqlstate in {"23503", "23505", "23514", "P0001"}, exc.sqlstate
                        if message:
                            assert message in str(exc), str(exc)
                        return
                    raise AssertionError("PlanVersion Review guard accepted forbidden write")

                reject(
                    "UPDATE plm.pln_plan_versions SET calendar_ref='STANDARD' "
                    "WHERE plan_version_id=%s", (version,),
                    "PlanVersion update is outside Review Owner",
                )
                reject(
                    "UPDATE plm.pln_plan_versions SET version_state='RESTRICTED' "
                    "WHERE plan_version_id=%s", (version,),
                    "PlanVersion update is outside Review Owner",
                )
                reject("TRUNCATE plm.pln_plan_version_review_state_results CASCADE", (),
                       "PlanVersion Review history cannot be truncated")
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute(
                    "SELECT to_regclass('plm.pln_plan_version_review_state_results')"
                ).fetchone()[0] is None
                trigger_names = {row[0] for row in db.execute(
                    "SELECT tgname FROM pg_trigger WHERE tgrelid='plm.pln_plan_versions'::regclass "
                    "AND NOT tgisinternal").fetchall()}
                assert "trg_pln_plan_versions__owner" in trigger_names
                assert "trg_pln_plan_versions__review_update" not in trigger_names
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            print("PLAN_VERSION_REVIEW_SCHEMA_POSTGRESQL_PASS: 0189->0190, ORM drift=0, "
                  "empty downgrade/re-upgrade, real PlanVersion content/state update rejection, "
                  "event truncate rejection, owner/update/deferred-closure trigger install")
        finally:
            for name in reversed(created):
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    main(parser.parse_args().port)
