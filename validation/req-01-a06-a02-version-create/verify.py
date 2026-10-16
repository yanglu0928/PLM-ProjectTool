"""Windows 11/PostgreSQL 18 proof for atomic RequirementVersion creation."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import SqlAlchemyEvidenceRequirementSourceProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, RequirementAcceptanceDraft, RequirementSourceDraft,
    RequirementVersionCreateError, RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
evidence_helpers = runpy.run_path(str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))
seed_evidence = evidence_helpers["seed_evidence"]
PREVIOUS = "20261007_0118"


def expect(code: str, action) -> None:
    try:
        action()
    except RequirementVersionCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "req01a06a02_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        try:
            with connect(database) as db:
                pm = seed_user(db, "Requirement Version PM", "NONE", pm_token)
                impl = seed_user(db, "Requirement Version Implementer", "NONE", impl_token)
                customer = seed_user(db, "Requirement Version Customer", "NONE", customer_token)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQV01','reqv01','Requirement Version Project',%s) RETURNING project_id",
                    (pm,)).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('REQV02','reqv02','Other Project',%s) RETURNING project_id",
                    (pm,)).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                    "RETURNING department_id", (project,)).fetchone()[0]
                for actor, role in ((pm, "PROJECT_MANAGER"),
                                    (impl, "IMPLEMENTATION_MEMBER"),
                                    (customer, "CUSTOMER_MANAGER")):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                               "VALUES (%s,%s,%s,%s)", (project, actor, department, role))
                evidence = seed_evidence(db, project, pm)
                evidence2 = seed_evidence(db, project, pm)
                foreign_evidence = seed_evidence(db, other, pm)

            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository())
            common = dict(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization, receipts=SqlAlchemyIdempotencyReceipts(),
                clock=lambda: datetime.now(timezone.utc),
            )
            audit = AuditService(SqlAlchemyAuditRepository())
            identity = RequirementIdentityCreateService(
                **common, repository=SqlAlchemyRequirementIdentityCreateRepository(),
                audit=audit)
            roots = {
                name: identity.create_requirement(CreateRequirementIdentity(
                    pm_token, CSRF, uuid.uuid4(), project, code, str(uuid.uuid4())))
                for name, code in (("main", "REQ-VERSION"), ("race", "REQ-VERSION-RACE"),
                                   ("rollback", "REQ-VERSION-ROLLBACK"),
                                   ("direct", "REQ-VERSION-DIRECT"))
            }

            def service(*, target_audit=audit):
                return RequirementVersionCreateService(
                    **common, repository=SqlAlchemyRequirementVersionCreateRepository(),
                    audit=target_audit, survey_sources=object(), handover_sources=object(),
                    human_decisions=object(),
                    project_evidence=SqlAlchemyEvidenceRequirementSourceProof(),
                    capability_sources=object(),
                    fixed_evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                )

            def create(root, *, version=0, initial=True, base=None, source=evidence,
                       token=impl_token, key=None, target=None, statement="Requirement statement"):
                return (target or service()).create(CreateRequirementVersion(
                    token, CSRF, uuid.uuid4(), project, root.requirement_id,
                    version, initial, base, None, statement,
                    "Business rationale", "PLM", "HIGH", "MEDIUM",
                    "PENDING_CONFIRMATION",
                    (RequirementSourceDraft("PROJECT_EVIDENCE", source, None, (source,)),),
                    (RequirementAcceptanceDraft(
                        "Observable outcome", "Execute acceptance test", "Project data",
                        "Windows 11", "Acceptance report"),),
                    (), (), (), (), (), "Create immutable draft", key or str(uuid.uuid4()),
                ))

            expect("RESOURCE_NOT_FOUND", lambda: create(roots["main"], token=customer_token))
            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", lambda: create(roots["main"]))
            guard.enabled = True
            expect("REQUIREMENT_SOURCE_UNAVAILABLE",
                   lambda: create(roots["main"], source=foreign_evidence))

            first_key = str(uuid.uuid4())
            first = create(roots["main"], key=first_key)
            assert first.version_no == 1 and first.lock_version == 1
            assert create(roots["main"], key=first_key) == first
            expect("CONFLICT_IDEMPOTENCY", lambda: create(
                roots["main"], key=first_key, statement="Different statement"))
            expect("CONFLICT_VERSION", lambda: create(roots["main"]))
            second = create(roots["main"], version=1, initial=False,
                            base=first.requirement_version_id, source=evidence2)
            assert second.version_no == 2 and second.lock_version == 2
            assert second.supersedes_version_ref == first.requirement_version_id
            expect("CONFLICT_VERSION", lambda: create(
                roots["main"], version=2, initial=False,
                base=first.requirement_version_id, source=evidence2))

            def race(statement):
                try:
                    return create(roots["race"], statement=statement)
                except RequirementVersionCreateError as error:
                    return error.code
            with ThreadPoolExecutor(max_workers=2) as pool:
                raced = list(pool.map(race, ("Race statement A", "Race statement B")))
            assert sum(value == "CONFLICT_VERSION" for value in raced) == 1, raced

            failed_key = str(uuid.uuid4())
            expect("REQUIREMENT_UNAVAILABLE", lambda: create(
                roots["rollback"], key=failed_key,
                target=service(target_audit=FailedAudit())))
            recovered = create(roots["rollback"], key=failed_key)
            assert recovered.version_no == 1 and recovered.lock_version == 1

            with connect(database) as db:
                try:
                    with db.transaction():
                        db.execute("UPDATE plm.req_requirements SET updated_by=%s,"
                                   "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                                   "WHERE requirement_id=%s", (pm, roots["direct"].requirement_id))
                except psycopg.Error as error:
                    assert "has no immutable result" in str(error), str(error)
                else:
                    raise AssertionError("root bump committed without create result")
                try:
                    with db.transaction():
                        version = uuid.uuid4()
                        db.execute("INSERT INTO plm.req_requirement_versions("
                                   "requirement_version_id,requirement_id,project_id,version_no,"
                                   "statement,rationale,domain_name,priority,risk,"
                                   "requirement_classification,content_fingerprint,"
                                   "declared_source_count,declared_acceptance_count,"
                                   "declared_capability_count,declared_assumption_count,"
                                   "declared_exclusion_count,declared_dependency_count,"
                                   "declared_ai_task_count,created_by) VALUES "
                                   "(%s,%s,%s,1,'Direct','Direct rationale','PLM','HIGH','MEDIUM',"
                                   "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
                                   (version, roots["direct"].requirement_id, project, b"d"*32, pm))
                        db.execute("INSERT INTO plm.req_sources(requirement_version_id,"
                                   "requirement_id,project_id,ordinal,source_type,source_object_id) "
                                   "VALUES (%s,%s,%s,0,'HUMAN_DECISION',%s)",
                                   (version, roots["direct"].requirement_id, project, uuid.uuid4()))
                except psycopg.Error as error:
                    assert "no immutable create result" in str(error), str(error)
                else:
                    raise AssertionError("Version committed without create result")
                counts = db.execute(
                    "SELECT (SELECT count(*) FROM plm.req_requirement_versions),"
                    "(SELECT count(*) FROM plm.req_requirement_version_create_results),"
                    "(SELECT count(*) FROM plm.aud_events WHERE action='REQUIREMENT_VERSION_CREATED')"
                ).fetchone()
                assert counts == (4, 4, 4), counts

            command.check(cfg)
            try:
                command.downgrade(cfg, PREVIOUS)
            except RuntimeError as error:
                assert "history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("RequirementVersion history was downgraded")
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print("REQ_01_A06_A02_VERSION_CREATE_PASS: initial/base, Root ETag, idempotency, "
          "concurrency, rollback, Evidence isolation, closure, downgrade and drift verified "
          "on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
