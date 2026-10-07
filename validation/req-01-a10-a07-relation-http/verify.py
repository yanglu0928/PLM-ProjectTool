"""Windows 11/PostgreSQL 18 proof for RequirementRelation HTTP."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.api.relation_cursor import RequirementRelationCursorCodec
from plm_assistant.modules.requirement.api.relations import create_requirement_relation_router
from plm_assistant.modules.requirement.application.relations import RequirementRelationService
from plm_assistant.modules.requirement.infrastructure.relation_repository import SqlAlchemyRequirementRelationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_user, CSRF = helpers["connect"], helpers["seed_user"], helpers["CSRF"]
definition = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
seed_dependencies = definition["seed_dependencies"]
TOKENS = {"pm": b"p" * 32, "impl": b"i" * 32}


class Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token not in TOKENS.values()
                or require_csrf and csrf_token != CSRF):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers(name="pm", *, key=None, etag=None):
    value = {
        "origin": "https://plm.example.test",
        "cookie": "plm_session=" + TOKENS[name].hex(),
        "x-csrf-token": CSRF.hex(),
    }
    if key is not None:
        value["idempotency-key"] = key
    if etag is not None:
        value["if-match"] = etag
    return value


def body(source, target, kind="DEPENDS_ON"):
    return {
        "source": {"requirement_id": str(source[0]),
                   "requirement_version_id": str(source[1])},
        "target": {"requirement_id": str(target[0]),
                   "requirement_version_id": str(target[1])},
        "relation_type": kind,
    }


def expect(response, status):
    if response.status_code != status:
        raise AssertionError((status, response.status_code, response.text))
    return response


def main() -> None:
    database = "req01a10a07_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            pm = seed_user(db, "A07 PM", "NONE", TOKENS["pm"])
            impl = seed_user(db, "A07 Implementer", "NONE", TOKENS["impl"])
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (impl, "IMPLEMENTATION_MEMBER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,"
                    "department_id,project_role) VALUES (%s,%s,%s,%s)",
                    (ids["project"], actor, ids["department"], role),
                )
            roots = [uuid.uuid4() for _ in range(4)]
            versions = [uuid.uuid4() for _ in range(4)]
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for number, (root, version) in enumerate(
                        zip(roots, versions, strict=True), 1):
                    code = f"REQ-HTTP-{number}"
                    db.execute(
                        "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                        "requirement_code,requirement_code_normalized,created_by) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (root, ids["project"], code, code, pm),
                    )
                    db.execute(
                        "INSERT INTO plm.req_requirement_versions("
                        "requirement_version_id,requirement_id,project_id,version_no,"
                        "statement,rationale,domain_name,priority,risk,"
                        "requirement_classification,content_fingerprint,"
                        "declared_source_count,declared_acceptance_count,"
                        "declared_capability_count,declared_assumption_count,"
                        "declared_exclusion_count,declared_dependency_count,"
                        "declared_ai_task_count,created_by) VALUES (%s,%s,%s,1,"
                        "'Statement','Rationale','PLM','HIGH','MEDIUM',"
                        "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                        (version, root, ids["project"], bytes([number]) * 32, pm),
                    )
                db.execute("SET LOCAL session_replication_role='origin'")
        runtime = create_database_runtime(url)
        guard = Guard()
        service = RequirementRelationService(
            unit_of_work=runtime.unit_of_work,
            write_access=SqlAlchemyProjectWriteAccess(),
            read_access=SqlAlchemyProjectReadAccess(), license_guard=guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ), repository=SqlAlchemyRequirementRelationRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        router = create_requirement_relation_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            relations=service, cursors=RequirementRelationCursorCodec(b"r" * 32),
        )
        refs = list(zip(roots, versions, strict=True))
        path = f"/api/v1/projects/{ids['project']}/requirement-relations"
        with TestClient(create_app(
            requirement_relation_router=router,
        ), base_url="https://plm.example.test") as client:
            create_key = str(uuid.uuid4())
            created = expect(client.post(
                path, headers=headers(key=create_key),
                json=body(refs[0], refs[1]),
            ), 201)
            old = created.json()["data"]["requirement_relation_id"]
            assert created.headers["etag"] == '"v0"'
            replay = expect(client.post(
                path, headers=headers(key=create_key),
                json=body(refs[0], refs[1]),
            ), 201)
            assert replay.json()["data"]["requirement_relation_id"] == old
            page1 = expect(client.get(
                path + "?page_size=1", headers=headers(),
            ), 200).json()["data"]
            assert page1["has_more"] is False
            expect(client.post(
                f"{path}/{old}:supersede",
                headers=headers(key=str(uuid.uuid4())),
                json=body(refs[1], refs[0]),
            ), 428)
            supersede_key = str(uuid.uuid4())
            replacement = expect(client.post(
                f"{path}/{old}:supersede",
                headers=headers(key=supersede_key, etag='"v0"'),
                json=body(refs[1], refs[0]),
            ), 201).json()["data"]
            replacement_id = replacement["requirement_relation_id"]
            replay = expect(client.post(
                f"{path}/{old}:supersede",
                headers=headers(key=supersede_key, etag='"v0"'),
                json=body(refs[1], refs[0]),
            ), 201).json()["data"]
            assert replay["requirement_relation_id"] == replacement_id
            expect(client.post(
                f"{path}/{replacement_id}:revoke",
                headers=headers(key=str(uuid.uuid4()), etag='"v1"'),
            ), 422)
            revoke_key = str(uuid.uuid4())
            revoked = expect(client.post(
                f"{path}/{replacement_id}:revoke",
                headers=headers(key=revoke_key, etag='"v0"'),
            ), 200).json()["data"]
            assert revoked["relation_state"] == "REVOKED"
            replay = expect(client.post(
                f"{path}/{replacement_id}:revoke",
                headers=headers(key=revoke_key, etag='"v0"'),
            ), 200).json()["data"]
            assert replay == revoked
            forward = expect(client.post(
                path, headers=headers(key=str(uuid.uuid4())),
                json=body(refs[2], refs[3]),
            ), 201).json()["data"]
            expect(client.post(
                path, headers=headers(key=str(uuid.uuid4())),
                json=body(refs[3], refs[2]),
            ), 422)
            symmetric = expect(client.post(
                path, headers=headers(key=str(uuid.uuid4())),
                json=body(refs[3], refs[2], "DUPLICATES"),
            ), 201).json()["data"]
            endpoints = sorted(
                (refs[2], refs[3]), key=lambda item: (item[0].bytes, item[1].bytes))
            assert symmetric["source"]["requirement_id"] == str(endpoints[0][0])
            page1 = expect(client.get(
                path + "?page_size=1", headers=headers(),
            ), 200).json()["data"]
            assert page1["has_more"] is True and page1["next_cursor"]
            page2 = expect(client.get(
                path + "?page_size=1&cursor=" + page1["next_cursor"],
                headers=headers(),
            ), 200).json()["data"]
            assert page2["items"] and page2["items"] != page1["items"]
            expect(client.post(
                path, headers=headers("impl", key=str(uuid.uuid4())),
                json=body(refs[0], refs[2]),
            ), 201)
            guard.denied = True
            expect(client.get(path, headers=headers()), 403)
            guard.denied = False
        with connect(database) as db:
            states = dict(db.execute(
                "SELECT requirement_relation_id,relation_state FROM "
                "plm.req_relations"
            ).fetchall())
            assert states[uuid.UUID(old)] == "SUPERSEDED"
            assert states[uuid.UUID(replacement_id)] == "REVOKED"
            assert states[uuid.UUID(forward["requirement_relation_id"])] == "ACTIVE"
            actions = dict(db.execute(
                "SELECT action,count(*) FROM plm.aud_events WHERE action LIKE "
                "'REQUIREMENT_RELATION_%' GROUP BY action"
            ).fetchall())
            assert actions == {
                "REQUIREMENT_RELATION_CREATED": 5,
                "REQUIREMENT_RELATION_REVOKED": 1,
                "REQUIREMENT_RELATION_SUPERSEDED": 1,
            }, actions
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation LIKE 'V1_REQ_RELATION_%'"
            ).fetchone()[0] == 6
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(sql.Identifier(database)))
    print(
        "REQ_01_A10_A07_RELATION_HTTP_PASS: four frozen HTTP operations, "
        "dedicated cursor, canonical endpoints, DAG rejection, strong If-Match, "
        "replay, role, License, Audit and drift verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
