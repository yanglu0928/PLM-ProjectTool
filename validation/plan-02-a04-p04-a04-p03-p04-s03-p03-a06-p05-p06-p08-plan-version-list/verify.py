"""Synthetic Win11/PG18 HTTP verification for PLAN_VERSION_LIST."""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone
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
from plm_assistant.modules.plan.api.list_plan_versions import create_plan_version_list_router
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec
from plm_assistant.modules.plan.application.list_plan_versions import PlanVersionListService
from plm_assistant.modules.plan.infrastructure.plan_version_list_repository import SqlAlchemyPlanVersionListRepository
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


PROJECT, OTHER_PROJECT, MANAGER = (uuid.uuid4() for _ in range(3))
PLAN, OTHER_PLAN = uuid.uuid4(), uuid.uuid4()
VERSIONS = [uuid.uuid4() for _ in range(3)]


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")


def main(port: int) -> None:
    def connect(name: str):
        return psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                               dbname=name, autocommit=True, connect_timeout=5)

    db_name = "plnlist_" + uuid.uuid4().hex[:10]
    created = False
    with connect("postgres") as admin:
        try:
            admin.execute(f'CREATE DATABASE "{db_name}"')
            created = True
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=port, database=db_name))
            command.upgrade(config, "head")
            command.check(config)
            with connect(db_name) as db, db.transaction():
                for user, name in ((MANAGER, "synthetic plan list manager"),):
                    db.execute("INSERT INTO plm.auth_users(user_id,username_display,username_normalized) VALUES (%s,%s,%s)",
                               (user, name, name))
                suffix = db_name[-6:]
                for project, code in ((PROJECT, "PL" + suffix), (OTHER_PROJECT, "PO" + suffix)):
                    db.execute("INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)",
                               (project, code, code.lower(), "Synthetic " + code, MANAGER))
                for project, plan in ((PROJECT, PLAN), (PROJECT, OTHER_PLAN)):
                    db.execute("INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) VALUES (%s,%s,%s,%s)",
                               (plan, project, "Synthetic plan", MANAGER))
                    db.execute("INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) SELECT plan_id,project_id,name,created_at FROM plm.pln_plans WHERE plan_id=%s", (plan,))
                for number, version in enumerate(VERSIONS, 1):
                    db.execute("INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,version_no,created_by) VALUES (%s,%s,%s,%s,%s)",
                               (version, PLAN, PROJECT, number, MANAGER))

            engine = create_engine(URL.create("postgresql+psycopg", username="poc_admin",
                                              host="127.0.0.1", port=port, database=db_name))
            try:
                uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine, expire_on_commit=False))
                access, license_guard, authz = Mock(), Mock(), Mock()
                access.authenticated_user.return_value = MANAGER
                license_guard.require_valid.return_value = object()
                authz.require_in_transaction.side_effect = lambda tx, *, user_id, project_id, operation: AuthorizedProjectAction(user_id, project_id, operation, "PROJECT_MANAGER")
                service = PlanVersionListService(
                    unit_of_work=uow, access=access, license_guard=license_guard,
                    authorization=authz, repository=SqlAlchemyPlanVersionListRepository())
                router = create_plan_version_list_router(
                    sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
                    reads=service, cursors=PlanVersionListCursorCodec(b"v" * 32))
                with TestClient(create_app(plan_version_list_router=router),
                                base_url="https://plm.example.test") as client:
                    path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions"
                    headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                               "origin": "https://plm.example.test"}
                    pages, cursor = [], None
                    while True:
                        params = {"page_size": "1"}
                        if cursor:
                            params["cursor"] = cursor
                        response = client.get(path, params=params, headers=headers)
                        assert response.status_code == 200, response.text
                        data = response.json()["data"]
                        pages.extend(data["items"])
                        cursor = data["next_cursor"]
                        if not data["has_more"]:
                            break
                    assert [row["version_no"] for row in pages] == [3, 2, 1]
                    assert len({row["plan_version_id"] for row in pages}) == 3
                    last_cursor = PlanVersionListCursorCodec(b"v" * 32).encode(
                        session_token=b"s" * 32, project_id=PROJECT,
                        plan_id=PLAN, page_size=1, version_no=2)
                    wrong_plan = client.get(
                        f"/api/v1/projects/{PROJECT}/plans/{OTHER_PLAN}/versions",
                        params={"page_size": "1", "cursor": last_cursor}, headers=headers)
                    assert wrong_plan.status_code == 400
                    cross_plan = client.get(
                        f"/api/v1/projects/{PROJECT}/plans/{OTHER_PLAN}/versions",
                        headers=headers)
                    assert cross_plan.status_code == 200
                    assert cross_plan.json()["data"]["items"] == []
                    print("PLAN_VERSION_LIST Win11/PG18 HTTP pagination PASS; synthetic auth/License/Project policy")
            finally:
                engine.dispose()
        finally:
            if created:
                with connect("postgres") as admin:
                    admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    main(parser.parse_args().port)
