"""Synthetic Windows/PG18 SQL + HTTP verification for PLAN_VERSION_GET."""
from __future__ import annotations
import argparse
import uuid
from unittest.mock import Mock
import psycopg
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.read_plan_version import create_plan_version_read_router
from plm_assistant.modules.plan.application.read_plan_version import PlanVersionReadService
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import SqlAlchemyPlanVersionReadRepository
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction

PROJECT, USER, PLAN, VERSION = (uuid.uuid4() for _ in range(4))
class Sessions:
    def validate(self, token):
        if token != b"s" * 32: raise SessionError("AUTH_SESSION_EXPIRED")

def main(port: int) -> None:
    def connect(name):
        return psycopg.connect(host="127.0.0.1", port=port, user="poc_admin", dbname=name, autocommit=True, connect_timeout=5)
    db_name = "plnread_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        try:
            admin.execute(f'CREATE DATABASE "{db_name}"')
            config = create_migration_config(URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=port, database=db_name))
            command.upgrade(config, "head"); command.check(config)
            with connect(db_name) as db, db.transaction():
                db.execute("INSERT INTO plm.auth_users(user_id,username_display,username_normalized) VALUES (%s,%s,%s)", (USER, "synthetic plan reader", "synthetic plan reader"))
                suffix = db_name[-6:]; code = "PR" + suffix
                db.execute("INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)", (PROJECT, code, code.lower(), "Synthetic Plan", USER))
                db.execute("INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) VALUES (%s,%s,%s,%s)", (PLAN, PROJECT, "Synthetic plan", USER))
                db.execute("INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) SELECT plan_id,project_id,name,created_at FROM plm.pln_plans WHERE plan_id=%s", (PLAN,))
                db.execute("INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) VALUES (%s,%s,%s,1,%s)", (VERSION, PLAN, PROJECT, USER))
            engine = create_engine(URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=port, database=db_name))
            try:
                runtime = Mock(); runtime.unit_of_work = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine, expire_on_commit=False))
                access, licenses, authz = Mock(), Mock(), Mock()
                access.authenticated_user.return_value = USER; licenses.require_valid.return_value = object()
                authz.require_in_transaction.side_effect = lambda tx, *, user_id, project_id, operation: AuthorizedProjectAction(user_id, project_id, operation, "PROJECT_MANAGER")
                service = PlanVersionReadService(unit_of_work=runtime.unit_of_work, access=access, license_guard=licenses,
                    authorization=authz, repository=SqlAlchemyPlanVersionReadRepository())
                router = create_plan_version_read_router(sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]), reads=service)
                with TestClient(create_app(plan_version_read_router=router), base_url="https://plm.example.test") as client:
                    path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions/{VERSION}"
                    headers = {"cookie": "plm_session=" + (b"s" * 32).hex(), "origin": "https://plm.example.test"}
                    got = client.get(path, headers=headers)
                    assert got.status_code == 200, got.text
                    body = got.json()["data"]
                    assert body["plan_version_id"] == str(VERSION) and body["calendar_ref"] is None
                    assert body["approved_solution_refs"] == [] and body["wbs_items"] == []
                    assert body["dependencies"] == [] and body["milestones"] == [] and body["exclusions"] == []
                    wrong = client.get(f"/api/v1/projects/{PROJECT}/plans/{uuid.uuid4()}/versions/{VERSION}", headers=headers)
                    assert wrong.status_code == 404, wrong.text
                print("PLAN_VERSION_GET Windows/PG18 SQL + HTTP PASS; synthetic Session/License/Project authorization")
            finally: engine.dispose()
        finally:
            admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, required=True); main(parser.parse_args().port)
