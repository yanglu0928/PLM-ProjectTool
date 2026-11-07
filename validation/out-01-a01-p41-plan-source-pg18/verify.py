"""Hosted PostgreSQL 18 probe for PlanVersion Output owner lookup."""
from __future__ import annotations

import argparse
import json
import re
import uuid
from types import SimpleNamespace

import psycopg
from psycopg import sql
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.plan.application.read_plan_version import (
    PlanOutputSourceProjection, PlanVersionReadService,
)
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import (
    SqlAlchemyPlanVersionReadRepository,
)


class Authorization:
    def require_in_transaction(self, transaction, *, user_id, project_id, operation):
        if operation != "PLAN_VERSION_GET":
            raise AssertionError("unexpected Plan permission operation")
        return SimpleNamespace(
            user_id=user_id, project_id=project_id, operation=operation,
        )


def _admin_dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("P41 PG18 probe requires a loopback port and numeric run id")

    db_name = "plm_p41_source_" + args.run_id[-10:]
    project_a, project_b, plan_a = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    version_old, version_exact, version_other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    actor = uuid.uuid4()
    engine = None
    created = False
    result = {"status": "INCOMPLETE", "exact_version_scope": "PENDING",
              "cross_project_isolation": "PENDING", "postgresql_major": None}
    try:
        with psycopg.connect(_admin_dsn(args.port), autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(db_name)))
            created = True
        engine = create_engine(URL.create(
            "postgresql+psycopg", username="postgres", host="127.0.0.1",
            port=args.port, database=db_name,
        ))
        with engine.begin() as connection:
            major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
            result["postgresql_major"] = major
            if major != 18:
                raise AssertionError("P41 probe requires PostgreSQL 18")
            connection.exec_driver_sql("CREATE SCHEMA plm")
            connection.exec_driver_sql(
                "CREATE TABLE plm.pln_plan_versions ("
                "plan_version_id uuid PRIMARY KEY, project_id uuid NOT NULL, "
                "plan_id uuid NOT NULL)"
            )
            connection.execute(
                text("INSERT INTO plm.pln_plan_versions "
                     "(plan_version_id, project_id, plan_id) "
                     "VALUES (:version, :project, :plan)"),
                [
                    {"version": version_old, "project": project_a, "plan": plan_a},
                    {"version": version_exact, "project": project_a, "plan": plan_a},
                    {"version": version_other, "project": project_b, "plan": uuid.uuid4()},
                ],
            )

        repository = SqlAlchemyPlanVersionReadRepository()
        calls = []
        views = {
            version_old: (1, "older-version"),
            version_exact: (2, "exact-version"),
        }

        def fixed_snapshot(transaction, *, project_id, plan_id, plan_version_id):
            calls.append((transaction, project_id, plan_id, plan_version_id))
            version_no, label = views[plan_version_id]
            return SimpleNamespace(
                plan_version_id=plan_version_id, plan_id=plan_id,
                project_id=project_id, version_no=version_no,
                version_state="APPROVED",
                snapshot={
                    "calendar_ref": None, "approved_solution_refs": [],
                    "wbs_items": [{"label": label}], "dependencies": [],
                    "milestones": [], "exclusions": [],
                },
            )

        repository.get_current = fixed_snapshot
        service = PlanVersionReadService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=Authorization(), repository=repository,
        )
        with Session(engine) as session, session.begin():
            transaction = SimpleNamespace(session=session)
            projection = service.read_output_source(
                transaction, actor_id=actor, project_id=project_a,
                plan_version_id=version_exact,
            )
            if (type(projection) is not PlanOutputSourceProjection
                    or projection.plan_version_id != version_exact
                    or projection.project_id != project_a
                    or projection.version_state != "APPROVED"
                    or projection.fields["version_no"] != 2
                    or projection.fields["wbs_items"] != [{"label": "exact-version"}]):
                raise AssertionError("exact PlanVersion projection mismatch")
            if calls != [(transaction, project_a, plan_a, version_exact)]:
                raise AssertionError("repository did not derive the exact owning plan")

            before = len(calls)
            try:
                service.read_output_source(
                    transaction, actor_id=actor, project_id=project_b,
                    plan_version_id=version_exact,
                )
            except Exception as error:
                if getattr(error, "code", None) != "RESOURCE_NOT_FOUND":
                    raise
            else:
                raise AssertionError("cross-project version unexpectedly resolved")
            if len(calls) != before:
                raise AssertionError("cross-project miss reached snapshot reconstruction")

        result.update({
            "status": "PASS_SCOPE_LIMITED",
            "exact_version_scope": "PASS",
            "cross_project_isolation": "PASS",
            "uses_real_pg_query": True,
            "customer_data": False,
            "migration_change": False,
        })
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with psycopg.connect(_admin_dsn(args.port), autocommit=True) as admin:
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))


if __name__ == "__main__":
    raise SystemExit(main())
