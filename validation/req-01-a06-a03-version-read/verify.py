"""Windows 11/PostgreSQL 18 proof for RequirementVersion reads."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

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
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadError, RequirementVersionReadQuery, RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
seed_evidence = runpy.run_path(str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))["seed_evidence"]


def expect(code, action):
    try: action()
    except RequirementVersionReadError as error: assert error.code == code, (error.code, code)
    else: raise AssertionError("expected " + code)


def main() -> None:
    database = "req01a06a03_" + uuid.uuid4().hex[:8]
    tokens = {"pm": b"p"*32, "impl": b"i"*32, "customer": b"c"*32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url); command.upgrade(cfg, "head"); command.check(cfg)
        runtime = create_database_runtime(url)
        try:
            with connect(database) as db:
                actors = {name: seed_user(db, "Read " + name, "NONE", token)
                          for name, token in tokens.items()}
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('REQR01','reqr01','Read Project',%s) RETURNING project_id", (actors["pm"],)).fetchone()[0]
                other = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('REQR02','reqr02','Other Project',%s) RETURNING project_id", (actors["pm"],)).fetchone()[0]
                dept = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'BUS','bus','Business') RETURNING department_id", (project,)).fetchone()[0]
                for name, role in (("pm","PROJECT_MANAGER"),("impl","IMPLEMENTATION_MEMBER"),("customer","CUSTOMER_MEMBER")):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (project, actors[name], dept, role))
                evidence1, evidence2 = seed_evidence(db, project, actors["pm"]), seed_evidence(db, project, actors["pm"])
            guard = Guard(); authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
            common = dict(unit_of_work=runtime.unit_of_work, license_guard=guard, authorization=authorization, clock=lambda: datetime.now(timezone.utc))
            creator = RequirementIdentityCreateService(**common, access=SqlAlchemyProjectWriteAccess(), receipts=SqlAlchemyIdempotencyReceipts(), repository=SqlAlchemyRequirementIdentityCreateRepository(), audit=AuditService(SqlAlchemyAuditRepository()))
            root = creator.create_requirement(CreateRequirementIdentity(tokens["pm"], CSRF, uuid.uuid4(), project, "REQ-READ", str(uuid.uuid4())))
            version_creator = RequirementVersionCreateService(**common, access=SqlAlchemyProjectWriteAccess(), receipts=SqlAlchemyIdempotencyReceipts(), repository=SqlAlchemyRequirementVersionCreateRepository(), audit=AuditService(SqlAlchemyAuditRepository()), survey_sources=object(), handover_sources=object(), human_decisions=object(), project_evidence=SqlAlchemyEvidenceRequirementSourceProof(), capability_sources=object(), fixed_evidence=SqlAlchemyEvidenceFixedSourceRepository())
            def create(evidence, lock, initial, base, statement):
                return version_creator.create(CreateRequirementVersion(tokens["impl"], CSRF, uuid.uuid4(), project, root.requirement_id, lock, initial, base, None, statement, "Rationale", "PLM", "HIGH", "MEDIUM", "PENDING_CONFIRMATION", (RequirementSourceDraft("PROJECT_EVIDENCE", evidence, None, (evidence,)),), (RequirementAcceptanceDraft("Outcome", "Method", "Data", "Windows 11", "Report"),), (), ("Assumption",), ("Exclusion",), ("Dependency",), (), "Read fixture", str(uuid.uuid4())))
            first = create(evidence1, 0, True, None, "First statement")
            second = create(evidence2, 1, False, first.requirement_version_id, "Second statement")
            reads = RequirementVersionReadService(**common, access=SqlAlchemyProjectReadAccess(), repository=SqlAlchemyRequirementVersionReadRepository())
            def query(name="customer", project_id=project, token=None):
                return RequirementVersionReadQuery(token or tokens[name], uuid.uuid4(), project_id)
            before = None
            with connect(database) as db:
                before = db.execute("SELECT (SELECT count(*) FROM plm.aud_events),(SELECT count(*) FROM plm.plt_idempotency_receipts),(SELECT count(*) FROM plm.req_requirement_versions)").fetchone()
            page1 = reads.list_versions(query(), requirement_id=root.requirement_id, page_size=1)
            assert page1.has_more and page1.items[0].requirement_version_id == second.requirement_version_id and page1.next_version_no == 2
            page2 = reads.list_versions(query("pm"), requirement_id=root.requirement_id, page_size=1, after_version_no=page1.next_version_no)
            assert not page2.has_more and page2.items[0].requirement_version_id == first.requirement_version_id
            detail = reads.get_version(query("impl"), requirement_id=root.requirement_id, requirement_version_id=second.requirement_version_id)
            assert detail.statement == "Second statement"
            assert [x.ordinal for x in detail.sources] == [0]
            assert [(x.evidence_id, x.ordinal) for x in detail.sources[0].evidence_refs] == [(evidence2, 0)]
            assert [x.text for x in detail.assumptions] == ["Assumption"]
            assert [x.text for x in detail.exclusions] == ["Exclusion"]
            assert [x.text for x in detail.dependencies] == ["Dependency"]
            expect("RESOURCE_NOT_FOUND", lambda: reads.get_version(query(project_id=other), requirement_id=root.requirement_id, requirement_version_id=second.requirement_version_id))
            expect("AUTH_ACCESS_DENIED", lambda: reads.list_versions(query(token=b"x"*32), requirement_id=root.requirement_id, page_size=10))
            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", lambda: reads.list_versions(query(), requirement_id=root.requirement_id, page_size=10))
            guard.enabled = True
            with connect(database) as db:
                after = db.execute("SELECT (SELECT count(*) FROM plm.aud_events),(SELECT count(*) FROM plm.plt_idempotency_receipts),(SELECT count(*) FROM plm.req_requirement_versions)").fetchone()
            assert after == before, (before, after)
            command.check(cfg)
        finally: runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("REQ_01_A06_A03_VERSION_READ_PASS: member list/get, keyset, complete ordered snapshot, isolation, denial, zero writes and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
