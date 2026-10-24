"""Windows 11/PostgreSQL 18 proof for Prototype production composition."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_prototype import (
    create_windows_prototype_routers,
)
from plm_assistant.entrypoints.windows_prototype_cursor import (
    PROTOTYPE_CURSOR_KEY_REFS,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import (
    SqlAlchemyPasswordIssueAccess,
)
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    ScryptPasswordHasher,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, seed_user, Guard, CSRF = (
    helpers["connect"], helpers["seed_user"], helpers["Guard"], helpers["CSRF"]
)
ORIGIN = "https://plm.example.test"


class Keys:
    def __init__(self) -> None:
        self.refs: list[str] = []

    def resolve_key(self, key_ref: str) -> bytes:
        self.refs.append(key_ref)
        return bytes([PROTOTYPE_CURSOR_KEY_REFS.index(key_ref) + 1]) * 32


def operations(routers) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for router in (
        routers.packages, routers.prototypes, routers.templates,
        routers.versions, routers.links, routers.review_submission,
    ):
        if router is not None:
            values.extend(
                (method, route.path)
                for route in router.routes
                for method in route.methods
                if method not in {"HEAD", "OPTIONS"}
            )
    return tuple(values)


def mounted_app(routers, review=None):
    return create_app(
        prototype_package_router=routers.packages,
        prototype_router=routers.prototypes,
        prototype_template_router=routers.templates,
        prototype_version_router=routers.versions,
        prototype_review_submission_router=routers.review_submission,
        requirement_prototype_link_router=routers.links,
        review_command_router=review,
    )


def main() -> None:
    database = "prt01a09a09_" + uuid.uuid4().hex[:8]
    token = b"p" * 32
    runtime = None
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            actor = seed_user(db, "Prototype HTTP PM", "DEPLOYMENT_ADMIN", token)
            project = db.execute(
                "INSERT INTO plm.prj_projects("
                "project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTHTTP','prthttp','Prototype HTTP Project',%s) "
                "RETURNING project_id", (actor,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments("
                "project_id,department_code,department_code_normalized,name) "
                "VALUES (%s,'BUS','bus','Business') RETURNING department_id",
                (project,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members("
                "project_id,user_id,department_id,project_role) "
                "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                (project, actor, department),
            )

        guard = Guard()
        audit = AuditService(SqlAlchemyAuditRepository())
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
            audit=audit, idempotency=SqlAlchemyIdempotencyReceipts(),
        )
        origins = LoginOriginPolicy([ORIGIN])

        with TestClient(create_app(), base_url=ORIGIN) as client:
            root = f"/api/v1/projects/{project}/prototype-packages"
            assert client.get(root).status_code == 404
            assert client.post(root).status_code == 404

        read_keys = Keys()
        read_only = create_windows_prototype_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=False, resolver=read_keys,
        )
        read_operations = operations(read_only)
        assert len(read_operations) == 9 and all(
            method == "GET" for method, _ in read_operations
        ), read_operations
        assert read_keys.refs == list(PROTOTYPE_CURSOR_KEY_REFS)
        read_headers = {"cookie": "plm_session=" + token.hex()}
        with TestClient(mounted_app(read_only), base_url=ORIGIN) as client:
            root = f"/api/v1/projects/{project}/prototype-packages"
            assert client.get(root, headers=read_headers).status_code == 200
            assert client.post(root, headers=read_headers).status_code == 405

        write_keys = Keys()
        write = create_windows_prototype_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=True, resolver=write_keys,
        )
        write_operations = operations(write)
        assert len(write_operations) == 26, write_operations
        assert sum(method == "GET" for method, _ in write_operations) == 9
        assert sum(method != "GET" for method, _ in write_operations) == 17
        review = create_windows_project_review_router(
            runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit,
        )
        write_headers = {
            **read_headers,
            "origin": ORIGIN,
            "x-csrf-token": CSRF.hex(),
        }
        package_root = f"/api/v1/projects/{project}/prototype-packages"
        prototype_root = f"/api/v1/projects/{project}/prototypes"
        with TestClient(mounted_app(write, review), base_url=ORIGIN) as client:
            package = client.post(
                package_root,
                headers={**write_headers, "idempotency-key": str(uuid.uuid4())},
                json={"name": "Implementation prototype package"},
            )
            assert package.status_code == 201, package.text
            package_id = package.json()["data"]["prototype_package_id"]
            assert client.get(
                f"{package_root}/{package_id}", headers=read_headers,
            ).status_code == 200

            prototype = client.post(
                prototype_root,
                headers={**write_headers, "idempotency-key": str(uuid.uuid4())},
                json={"name": "Approval workflow"},
            )
            assert prototype.status_code == 201, prototype.text
            prototype_id = prototype.json()["data"]["prototype_id"]
            assert client.get(
                f"{prototype_root}/{prototype_id}", headers=read_headers,
            ).status_code == 200

            members = client.post(
                f"{package_root}/{package_id}:set-members",
                headers={
                    **write_headers, "if-match": '"v0"',
                    "idempotency-key": str(uuid.uuid4()),
                },
                json={"prototype_ids": [prototype_id]},
            )
            assert members.status_code == 200, members.text
            renamed = client.patch(
                f"{package_root}/{package_id}",
                headers={**write_headers, "if-match": '"v1"'},
                json={"name": "Delivery prototype package"},
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.headers["etag"] == '"v2"'

            assert client.get(
                f"/api/v1/projects/{project}/prototype-templates",
                headers=read_headers,
            ).status_code == 200
            assert client.get(
                "/api/v1/global/prototype-templates", headers=read_headers,
            ).status_code == 200
            assert client.get(
                f"{prototype_root}/{prototype_id}/versions",
                headers=read_headers,
            ).status_code == 200
            assert client.get(
                f"/api/v1/projects/{project}/prototype-requirement-links",
                headers=read_headers,
            ).status_code == 200
            assert client.get(
                f"{prototype_root}/{prototype_id}/versions/{uuid.uuid4()}",
                headers=read_headers,
            ).status_code == 404

        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.prt_packages"
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.prt_prototypes"
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.prt_package_memberships"
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action LIKE 'PROTOTYPE_%'"
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation LIKE 'V1_PRT_%'"
            ).fetchone()[0] == 3
        command.check(cfg)
        print(
            "PRT_01_A09_A09_WINDOWS_COMPOSITION_PASS: default closed, nine "
            "read-only routes, 26 write-mode operations, PRT-03 unified Review "
            "registration, real Session/CSRF/License/authorization, package and "
            "prototype create/read/membership/mutation, templates/version/link "
            "reads, Audit/receipt and drift verified on Windows 11/PostgreSQL 18"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {}"
            ).format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
