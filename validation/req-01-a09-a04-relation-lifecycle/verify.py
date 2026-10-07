"""Windows 11/PostgreSQL 18 proof for RequirementRelation lifecycle."""

from __future__ import annotations

import runpy
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
    RequirementRelationService, RequirementVersionRef,
    RevokeRequirementRelation, SupersedeRequirementRelation,
)
from plm_assistant.modules.requirement.infrastructure.relation_repository import SqlAlchemyRequirementRelationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_user, Guard, CSRF = (
    helpers["connect"], helpers["seed_user"], helpers["Guard"], helpers["CSRF"])
definition = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
seed_dependencies = definition["seed_dependencies"]


def main() -> None:
    database = "req01a09a04_" + uuid.uuid4().hex[:8]
    token = b"p" * 32
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
            actor = seed_user(db, "Relation Lifecycle PM", "NONE", token)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                       (ids["project"], actor, ids["department"]))
            roots, versions = [uuid.uuid4() for _ in range(4)], [uuid.uuid4() for _ in range(4)]
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for n, (root, version) in enumerate(zip(roots, versions, strict=True), 1):
                    code = f"REQ-LIFE-{n}"
                    db.execute("INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,requirement_code_normalized,created_by) VALUES (%s,%s,%s,%s,%s)",
                               (root, ids["project"], code, code, actor))
                    db.execute("INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,version_no,statement,rationale,domain_name,priority,risk,requirement_classification,content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,created_by) VALUES (%s,%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM','PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                               (version, root, ids["project"], bytes([n]) * 32, actor))
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

        def create(source, target, kind):
            return service.create(CreateRequirementRelation(
                token, CSRF, uuid.uuid4(), ids["project"], source, target,
                kind, str(uuid.uuid4())))

        old = create(refs[0], refs[1], "DEPENDS_ON")
        supersede_key = str(uuid.uuid4())
        supersede_command = SupersedeRequirementRelation(
            token, CSRF, uuid.uuid4(), ids["project"],
            old.requirement_relation_id, refs[1], refs[0], "DEPENDS_ON",
            supersede_key)
        replacement = service.supersede(supersede_command)
        assert (replacement.source, replacement.target) == (refs[1], refs[0])
        assert service.supersede(supersede_command) == replacement
        try:
            service.revoke(RevokeRequirementRelation(
                token, CSRF, uuid.uuid4(), ids["project"],
                old.requirement_relation_id, str(uuid.uuid4())))
        except RequirementRelationError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else:
            raise AssertionError("superseded relation revoked")

        revoke_command = RevokeRequirementRelation(
            token, CSRF, uuid.uuid4(), ids["project"],
            replacement.requirement_relation_id, str(uuid.uuid4()))
        revoked = service.revoke(revoke_command)
        assert revoked.relation_state == "REVOKED" and revoked.lock_version == 1
        assert service.revoke(revoke_command) == revoked
        try:
            service.supersede(SupersedeRequirementRelation(
                token, CSRF, uuid.uuid4(), ids["project"],
                replacement.requirement_relation_id, refs[1], refs[2],
                "DEPENDS_ON", str(uuid.uuid4())))
        except RequirementRelationError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else:
            raise AssertionError("revoked relation superseded")

        existing = create(refs[2], refs[3], "RELATED_TO")
        old2 = create(refs[0], refs[3], "RELATED_TO")
        reused = service.supersede(SupersedeRequirementRelation(
            token, CSRF, uuid.uuid4(), ids["project"], old2.requirement_relation_id,
            refs[2], refs[3], "RELATED_TO", str(uuid.uuid4())))
        assert reused.requirement_relation_id == existing.requirement_relation_id

        with connect(database) as db:
            rows = db.execute("SELECT requirement_relation_id,relation_state,superseded_by_ref FROM plm.req_relations ORDER BY requirement_relation_id").fetchall()
            projected = {row[0]: (row[1], row[2]) for row in rows}
            assert projected[old.requirement_relation_id] == (
                "SUPERSEDED", replacement.requirement_relation_id)
            assert projected[replacement.requirement_relation_id] == ("REVOKED", None)
            assert projected[old2.requirement_relation_id] == (
                "SUPERSEDED", existing.requirement_relation_id)
            assert projected[existing.requirement_relation_id] == ("ACTIVE", None)
            actions = dict(db.execute("SELECT action,count(*) FROM plm.aud_events WHERE action LIKE 'REQUIREMENT_RELATION_%' GROUP BY action").fetchall())
            assert actions == {
                "REQUIREMENT_RELATION_CREATED": 4,
                "REQUIREMENT_RELATION_REVOKED": 1,
                "REQUIREMENT_RELATION_SUPERSEDED": 2,
            }, actions
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation LIKE 'V1_REQ_RELATION_%'").fetchone()[0] == 6
            assert db.execute("""
                SELECT operation, result_status, count(*)
                  FROM plm.plt_idempotency_receipts
                 WHERE operation LIKE 'V1_REQ_RELATION_%'
                 GROUP BY operation, result_status
                 ORDER BY operation
            """).fetchall() == [
                ("V1_REQ_RELATION_CREATE", 201, 3),
                ("V1_REQ_RELATION_REVOKE", 200, 1),
                ("V1_REQ_RELATION_SUPERSEDE", 201, 2),
            ]
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("REQ_01_A09_A04_RELATION_LIFECYCLE_PASS: revoke/supersede, old-edge DAG exclusion, active replacement reuse, immutable terminal replay, audit, receipts and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
