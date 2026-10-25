"""Disposable Windows 11/PostgreSQL proof for REQ-03 Trace target ownership."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import SqlAlchemyEvidenceRequirementSourceProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.create_identity import CreateRequirementIdentity, RequirementIdentityCreateService
from plm_assistant.modules.requirement.application.create_version import CreateRequirementVersion, RequirementAcceptanceDraft, RequirementSourceDraft, RequirementVersionCreateService
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.trace.application.target_proof import TraceProofQuery, TraceResourceVersionRef, TraceTargetProofError


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
seed_evidence = runpy.run_path(str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))["seed_evidence"]


def denied(code, action):
    try:
        action()
    except TraceTargetProofError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    database = "trc01a03p01_" + uuid.uuid4().hex[:8]
    token = b"p" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        try:
            with connect(database) as db:
                actor = seed_user(db, "Trace Requirement PM", "NONE", token)
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('TRCR01','trcr01','Trace Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('TRCR02','trcr02','Other Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'BUS','bus','Business') RETURNING department_id", (project,)).fetchone()[0]
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, actor, department))
                evidence = seed_evidence(db, project, actor)
            guard = Guard()
            authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
            common = dict(unit_of_work=runtime.unit_of_work, license_guard=guard, authorization=authorization, clock=lambda: datetime.now(timezone.utc))
            creator = RequirementIdentityCreateService(**common, access=SqlAlchemyProjectWriteAccess(), receipts=SqlAlchemyIdempotencyReceipts(), repository=SqlAlchemyRequirementIdentityCreateRepository(), audit=AuditService(SqlAlchemyAuditRepository()))
            root = creator.create_requirement(CreateRequirementIdentity(token, CSRF, uuid.uuid4(), project, "REQ-TRACE", str(uuid.uuid4())))
            versions = RequirementVersionCreateService(**common, access=SqlAlchemyProjectWriteAccess(), receipts=SqlAlchemyIdempotencyReceipts(), repository=SqlAlchemyRequirementVersionCreateRepository(), audit=AuditService(SqlAlchemyAuditRepository()), survey_sources=object(), handover_sources=object(), human_decisions=object(), project_evidence=SqlAlchemyEvidenceRequirementSourceProof(), capability_sources=object(), fixed_evidence=SqlAlchemyEvidenceFixedSourceRepository())
            version = versions.create(CreateRequirementVersion(token, CSRF, uuid.uuid4(), project, root.requirement_id, 0, True, None, None, "Trace statement", "Rationale", "PLM", "HIGH", "MEDIUM", "PENDING_CONFIRMATION", (RequirementSourceDraft("PROJECT_EVIDENCE", evidence, None, (evidence,)),), (RequirementAcceptanceDraft("Outcome", "Method", "Data", "Windows 11", "Report"),), (), (), (), (), (), "Trace fixture", str(uuid.uuid4())))
            reads = RequirementVersionReadService(**common, access=SqlAlchemyProjectReadAccess(), repository=SqlAlchemyRequirementVersionReadRepository())
            owner = RequirementVersionTraceOwner(reads)
            public = TraceResourceVersionRef("REQ-03", root.requirement_id, version.requirement_version_id)
            query = TraceProofQuery(token, uuid.uuid4())
            with connect(database) as db:
                before = db.execute("SELECT (SELECT count(*) FROM plm.aud_events),(SELECT count(*) FROM plm.plt_idempotency_receipts)").fetchone()
            with runtime.unit_of_work() as tx:
                ref = owner.resolve(tx, query, project, public)
                assert ref.project_id == project and ref.object_id == root.requirement_id
                assert owner.prove(tx, query, ref).ref == ref
                denied("RESOURCE_NOT_FOUND", lambda: owner.resolve(tx, query, other, public))
                denied("RESOURCE_NOT_FOUND", lambda: owner.resolve(tx, query, project, TraceResourceVersionRef("REQ-03", root.requirement_id, uuid.uuid4())))
                denied("RESOURCE_NOT_FOUND", lambda: owner.prove(tx, TraceProofQuery(b"x" * 32, uuid.uuid4()), ref))
                guard.enabled = False
                denied("LICENSE_OPERATION_DENIED", lambda: owner.prove(tx, query, ref))
                guard.enabled = True
            with connect(database) as db:
                after = db.execute("SELECT (SELECT count(*) FROM plm.aud_events),(SELECT count(*) FROM plm.plt_idempotency_receipts)").fetchone()
            assert after == before, (before, after)
            command.check(cfg)
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("TRC_01_A03_P01_REQUIREMENT_OWNER_PASS: same transaction, fixed DRAFT, project/session/license denial, zero Trace writes, drift")


if __name__ == "__main__":
    main()
