"""Windows 11/PostgreSQL 18 proof for RequirementRelation create/list."""

from __future__ import annotations

import runpy
import threading
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.relations import (
    CreateRequirementRelation, RequirementRelationError,
    RequirementRelationQuery, RequirementRelationService, RequirementVersionRef,
)
from plm_assistant.modules.requirement.infrastructure.relation_repository import SqlAlchemyRequirementRelationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_user, Guard, CSRF = (
    helpers["connect"], helpers["seed_user"], helpers["Guard"], helpers["CSRF"])
definition = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
seed_dependencies = definition["seed_dependencies"]


def main() -> None:
    database = "req01a09a03_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            pm = seed_user(db, "Relation PM", "NONE", pm_token)
            impl = seed_user(db, "Relation Implementer", "NONE", impl_token)
            customer = seed_user(db, "Relation Customer", "NONE", customer_token)
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (impl, "IMPLEMENTATION_MEMBER"),
                                (customer, "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], actor, ids["department"], role))
            roots, versions = [uuid.uuid4() for _ in range(5)], [uuid.uuid4() for _ in range(5)]
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for n, (root, version) in enumerate(zip(roots, versions, strict=True), 1):
                    code = f"REQ-OWNER-{n}"
                    db.execute("INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,requirement_code_normalized,created_by) VALUES (%s,%s,%s,%s,%s)",
                               (root, ids["project"], code, code, pm))
                    db.execute("INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,version_no,statement,rationale,domain_name,priority,risk,requirement_classification,content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,created_by) VALUES (%s,%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM','PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                               (version, root, ids["project"], bytes([n]) * 32, pm))
                db.execute("SET LOCAL session_replication_role='origin'")

        runtime = create_database_runtime(url)
        project_repo = SqlAlchemyProjectAuthorizationRepository()
        service = RequirementRelationService(
            unit_of_work=runtime.unit_of_work,
            write_access=SqlAlchemyProjectWriteAccess(),
            read_access=SqlAlchemyProjectReadAccess(), license_guard=Guard(),
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work, repository=project_repo),
            repository=SqlAlchemyRequirementRelationRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=AuditService(SqlAlchemyAuditRepository()))
        refs = [RequirementVersionRef(root, version)
                for root, version in zip(roots, versions, strict=True)]

        def create(source, target, relation_type, *, token=pm_token, key=None):
            return service.create(CreateRequirementRelation(
                token, CSRF, uuid.uuid4(), ids["project"], source, target,
                relation_type, key or str(uuid.uuid4())))

        first = create(refs[0], refs[1], "DEPENDS_ON")
        try:
            create(refs[1], refs[0], "DEPENDS_ON")
        except RequirementRelationError as error:
            assert error.code == "REQUIREMENT_RELATION_CYCLE", error.code
        else:
            raise AssertionError("directed cycle accepted")

        reversed_pair = sorted(
            (refs[0], refs[2]),
            key=lambda ref: (ref.requirement_id.bytes,
                             ref.requirement_version_id.bytes), reverse=True)
        symmetric = create(reversed_pair[0], reversed_pair[1], "DUPLICATES",
                           token=impl_token)
        same = create(reversed_pair[1], reversed_pair[0], "DUPLICATES",
                      token=impl_token)
        assert same.requirement_relation_id == symmetric.requirement_relation_id
        create(refs[0], refs[3], "RELATED_TO", token=impl_token)

        page1 = service.list(RequirementRelationQuery(
            customer_token, uuid.uuid4(), ids["project"]), page_size=2)
        assert len(page1.items) == 2 and page1.has_more
        page2 = service.list(RequirementRelationQuery(
            customer_token, uuid.uuid4(), ids["project"]), page_size=2,
            after_relation_id=page1.next_relation_id)
        assert len(page2.items) == 1 and not page2.has_more
        assert not ({item.requirement_relation_id for item in page1.items}
                    & {item.requirement_relation_id for item in page2.items})

        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        outcome_lock = threading.Lock()

        def concurrent(source, target, token):
            barrier.wait()
            try:
                create(source, target, "PARENT_OF", token=token)
                result = "CREATED"
            except RequirementRelationError as error:
                result = error.code
            with outcome_lock:
                outcomes.append(result)

        threads = [
            threading.Thread(target=concurrent,
                             args=(refs[3], refs[4], pm_token)),
            threading.Thread(target=concurrent,
                             args=(refs[4], refs[3], impl_token)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
            assert not thread.is_alive()
        assert sorted(outcomes) == ["CREATED", "REQUIREMENT_RELATION_CYCLE"], outcomes

        try:
            create(RequirementVersionRef(uuid.uuid4(), refs[0].requirement_version_id),
                   refs[1], "RELATED_TO")
        except RequirementRelationError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else:
            raise AssertionError("mismatched Requirement/Version endpoint accepted")
        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.req_relations WHERE relation_state='ACTIVE'").fetchone()[0] == 4
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='REQUIREMENT_RELATION_CREATED'").fetchone()[0] == 4
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_REQ_RELATION_CREATE'").fetchone()[0] == 5
        assert first.relation_state == "ACTIVE"
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("REQ_01_A09_A03_RELATION_CREATE_LIST_PASS: authorization, fixed endpoints, canonical symmetric idempotency, pagination, typed DAG, concurrent inverse edges, audit and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
