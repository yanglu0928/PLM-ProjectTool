"""Win11/PG18 synthetic lock-and-latest proof for Plan Review readiness."""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanReviewReadinessDenied, PlanVersionReviewReadinessQuery,
    PlanVersionReviewReadinessService,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionCoverageSummary, PlanVersionValidationReport,
)
from plm_assistant.modules.plan.infrastructure.plan_review_readiness_repository import (
    SqlAlchemyPlanVersionReviewReadinessRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


USER = "poc_admin"
PREVIOUS = "20261026_0189"


def main(port: int) -> None:
    def connect(name: str) -> psycopg.Connection:
        return psycopg.connect(host="127.0.0.1", port=port, user=USER,
                               dbname=name, autocommit=True, connect_timeout=5)

    def migration(name: str):
        return create_migration_config(URL.create(
            "postgresql+psycopg", username=USER, host="127.0.0.1",
            port=port, database=name))

    db_name = "plnrevread_" + uuid.uuid4().hex[:10]
    created = False
    with connect("postgres") as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            created = True
            config = migration(db_name)
            command.upgrade(config, "head")
            command.check(config)
            project, plan = uuid.uuid4(), uuid.uuid4()
            version_ids = (uuid.uuid4(), uuid.uuid4())
            with connect(db_name) as db, db.transaction():
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES (%s,%s) RETURNING user_id",
                    ("Synthetic Plan Review Readiness", "synthetic plan review readiness " + db_name),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (project, "PRRD" + db_name[-6:], "prrd" + db_name[-6:],
                     "Synthetic readiness", actor),
                )
                name = "Synthetic readiness plan"
                created_at = db.execute(
                    "INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) "
                    "VALUES (%s,%s,%s,%s) RETURNING created_at",
                    (plan, project, name, actor),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                    "VALUES (%s,%s,%s,%s)", (plan, project, name, created_at),
                )
                for number, version_id in enumerate(version_ids, start=1):
                    db.execute(
                        "INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (version_id, plan, project, number, actor),
                    )

            engine = create_engine(URL.create(
                "postgresql+psycopg", username=USER, host="127.0.0.1",
                port=port, database=db_name))
            try:
                repository = SqlAlchemyPlanVersionReviewReadinessRepository()
                evaluator = Mock()
                checked_at = datetime.now(timezone.utc)
                report = PlanVersionValidationReport(
                    True, (), (), PlanVersionCoverageSummary(0, 0, 0, 0, 0, 0, 0, 0),
                    checked_at)
                evaluator.evaluate_snapshot_in_transaction.return_value = (b"r" * 32, report)
                service = PlanVersionReviewReadinessService(
                    repository=repository, evaluator=evaluator)
                with Session(engine) as session, session.begin():
                    tx = SimpleNamespace(session=session)
                    proof = service.prove_in_transaction(tx, query=
                        PlanVersionReviewReadinessQuery(
                            b"s" * 32, uuid.uuid4(), project, plan, version_ids[1]))
                    assert proof.plan_version_id == version_ids[1]
                    assert proof.version_no == 2
                    try:
                        service.prove_in_transaction(tx, query=
                            PlanVersionReviewReadinessQuery(
                                b"s" * 32, uuid.uuid4(), project, plan, version_ids[0]))
                    except PlanReviewReadinessDenied:
                        pass
                    else:
                        raise AssertionError("older DRAFT PlanVersion was considered current")
                    assert evaluator.evaluate_snapshot_in_transaction.call_count == 1
                    assert session.execute(
                        text("SELECT count(*) FROM plm.aud_events "
                             "WHERE target_object_type='PLN-02' AND target_object_id=:version"),
                        {"version": version_ids[1]},
                    ).scalar_one() == 0
                print("PLAN_VERSION_REVIEW_READINESS_PG_PASS: real Plan identity/version row locks, "
                      "latest-DRAFT binding, same-transaction evaluator, no Audit write")
            finally:
                engine.dispose()
        finally:
            if created:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (db_name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    main(parser.parse_args().port)
