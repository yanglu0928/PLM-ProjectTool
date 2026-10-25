"""Isolated Win11/PG18 migration and Approved-pointer guard verification.

Synthetic identity and Draft Plan fixtures only. This verifies schema and
database-enforced boundaries; it does not claim a real approval workflow.
"""

from __future__ import annotations

import argparse
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


USER = "poc_admin"


def main(port: int) -> None:
    def connect(name: str) -> psycopg.Connection:
        return psycopg.connect(host="127.0.0.1", port=port, user=USER,
                               dbname=name, autocommit=True, connect_timeout=5)

    def config(name: str):
        return create_migration_config(URL.create(
            "postgresql+psycopg", username=USER, host="127.0.0.1",
            port=port, database=name))

    db_name = "plnapprptr_" + uuid.uuid4().hex[:10]
    created = False
    with connect("postgres") as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            created = True
            cfg = config(db_name)
            command.upgrade(cfg, "head")
            command.check(cfg)

            project, plan, version, actor = (uuid.uuid4() for _ in range(4))
            tag = db_name[-6:]
            with connect(db_name) as db, db.transaction():
                username = "synthetic approved-pointer " + db_name
                db.execute(
                    "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) VALUES (%s,%s,%s)",
                    (actor, username, username),
                )
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)",
                    (project, "PAP" + tag, "pap" + tag, "Synthetic pointer schema", actor),
                )
                db.execute(
                    "INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) VALUES (%s,%s,%s,%s)",
                    (plan, project, "Synthetic Draft Plan", actor),
                )
                db.execute(
                    "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) SELECT plan_id,project_id,name,created_at FROM plm.pln_plans WHERE plan_id=%s",
                    (plan,),
                )
                db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) VALUES (%s,%s,%s,1,%s)",
                    (version, plan, project, actor),
                )

            with connect(db_name) as db:
                # Plan identity remains closed except for the narrow pointer owner.
                with db.transaction():
                    try:
                        db.execute("UPDATE plm.pln_plans SET name='forbidden' WHERE plan_id=%s", (plan,))
                        raise AssertionError("ordinary Plan UPDATE was accepted")
                    except psycopg.errors.RaiseException:
                        pass
                with db.transaction():
                    try:
                        db.execute(
                            "UPDATE plm.pln_plans SET current_approved_version_ref=%s,lock_version=lock_version+1 WHERE plan_id=%s",
                            (version, plan),
                        )
                        raise AssertionError("Draft version was accepted as Approved pointer")
                    except psycopg.errors.RaiseException:
                        pass
                with db.transaction():
                    try:
                        db.execute("TRUNCATE plm.pln_plan_version_review_state_results")
                        raise AssertionError("append-only Review result TRUNCATE was accepted")
                    except psycopg.errors.RaiseException:
                        pass

            # History-free round trip must preserve Draft data and restore drift-free head.
            command.downgrade(cfg, "20261026_0190")
            with connect(db_name) as db:
                assert db.execute(
                    "SELECT version_state FROM plm.pln_plan_versions WHERE plan_version_id=%s",
                    (version,),
                ).fetchone()[0] == "DRAFT"
            command.upgrade(cfg, "head")
            command.check(cfg)
            with connect(db_name) as db:
                # Existing Draft history allows downgrade, but any review-linked transition blocks it.
                assert db.execute("SELECT count(*) FROM plm.pln_plans WHERE plan_id=%s AND current_approved_version_ref IS NULL", (plan,)).fetchone()[0] == 1
            print("PASS: PG18 full migration chain/check, narrow Plan guard, Draft pointer rejection, append-only TRUNCATE, history-free downgrade/re-upgrade")
        finally:
            if created:
                with connect("postgres") as admin:
                    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db_name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    main(parser.parse_args().port)
