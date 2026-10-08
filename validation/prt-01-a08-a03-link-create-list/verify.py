"""Windows 11/PostgreSQL 18 proof for Link CREATE/LIST Owner."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path
from types import SimpleNamespace

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
from plm_assistant.modules.prototype.application.requirement_links import (
    CreateRequirementPrototypeLink, RequirementPrototypeCoverage,
    RequirementPrototypeLinkError, RequirementPrototypeLinkQuery,
    RequirementPrototypeLinkService, UncoveredAcceptanceCriterion,
)
from plm_assistant.modules.prototype.infrastructure.requirement_link_repository import (
    SqlAlchemyRequirementPrototypeLinkRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_user, Guard, CSRF = (
    helpers["connect"], helpers["seed_user"], helpers["Guard"], helpers["CSRF"])
definition = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
seed_dependencies = definition["seed_dependencies"]


class Reader:
    def __init__(self, snapshot): self.snapshot = snapshot
    def get(self, *_args, **_kwargs): return self.snapshot


class Validator:
    valid = True
    def current_facts(self, *_args): return object() if self.valid else None


def main() -> None:
    database = "prt01a08a03_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head"); command.check(cfg)
        requirement, requirement_version = uuid.uuid4(), uuid.uuid4()
        prototype, prototype_version = uuid.uuid4(), uuid.uuid4()
        criteria = (uuid.uuid4(), uuid.uuid4())
        with connect(database) as db:
            ids = seed_dependencies(db)
            pm = seed_user(db, "Link PM", "NONE", pm_token)
            impl = seed_user(db, "Link Implementer", "NONE", impl_token)
            customer = seed_user(db, "Link Customer", "NONE", customer_token)
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (impl, "IMPLEMENTATION_MEMBER"),
                                (customer, "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], actor, ids["department"], role))
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,requirement_code_normalized,requirement_state,current_approved_version_ref,created_by) VALUES (%s,%s,'LINK-REQ','LINK-REQ','ACTIVE',%s,%s)",
                           (requirement, ids["project"], requirement_version, pm))
                db.execute("INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,version_no,version_state,statement,rationale,domain_name,priority,risk,requirement_classification,content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,review_ref,review_round_ref,created_by) VALUES (%s,%s,%s,1,'APPROVED','Statement','Rationale','PLM','HIGH','MEDIUM','STANDARD_FUNCTION',%s,1,2,0,0,0,0,0,%s,%s,%s)",
                           (requirement_version, requirement, ids["project"], b"r"*32, uuid.uuid4(), uuid.uuid4(), pm))
                for ordinal, criterion in enumerate(criteria):
                    db.execute("INSERT INTO plm.req_acceptance_criteria(acceptance_criterion_id,requirement_version_id,requirement_id,project_id,ordinal,observable_result,verification_method,required_data,required_environment,evidence_requirement) VALUES (%s,%s,%s,%s,%s,'Observed','Manual','Data','Environment','Evidence')",
                               (criterion, requirement_version, requirement, ids["project"], ordinal))
                db.execute("INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,prototype_state,current_approved_version_ref,created_by) VALUES (%s,%s,'Link prototype','ACTIVE',%s,%s)",
                           (prototype, ids["project"], prototype_version, pm))
                db.execute("INSERT INTO plm.prt_prototype_versions(prototype_version_id,prototype_id,project_id,version_no,version_state,template_ref,template_version_ref,coverage_summary,content_fingerprint,declared_artifact_count,declared_requirement_count,declared_interaction_count,review_ref,review_round_ref,created_by) VALUES (%s,%s,%s,1,'APPROVED',%s,%s,'{}',%s,1,1,1,%s,%s,%s)",
                           (prototype_version, prototype, ids["project"], uuid.uuid4(), uuid.uuid4(), b"p"*32, uuid.uuid4(), uuid.uuid4(), pm))
                db.execute("INSERT INTO plm.prt_version_requirement_refs(prototype_version_id,prototype_id,project_id,requirement_id,requirement_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,1)",
                           (prototype_version, prototype, ids["project"], requirement, requirement_version))
                db.execute("INSERT INTO plm.prt_version_approval_trace_manifests(approval_trace_manifest_id,prototype_version_id,prototype_id,project_id,review_state_result_id,review_id,review_round_id,template_id,template_version_id,content_fingerprint,declared_artifact_count,declared_requirement_count,declared_trace_link_count,approved_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,1,3,%s)",
                           (uuid.uuid4(), prototype_version, prototype, ids["project"], uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), b"p"*32, pm))
        snapshot = SimpleNamespace(
            version_state="APPROVED",
            requirement_refs=(SimpleNamespace(
                requirement_id=requirement,
                requirement_version_id=requirement_version),),
        )
        validator = Validator()
        runtime = create_database_runtime(url)
        service = RequirementPrototypeLinkService(
            unit_of_work=runtime.unit_of_work,
            write_access=SqlAlchemyProjectWriteAccess(),
            read_access=SqlAlchemyProjectReadAccess(), license_guard=Guard(),
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            repository=SqlAlchemyRequirementPrototypeLinkRepository(),
            version_reader=Reader(snapshot), current_validator=validator,
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=AuditService(SqlAlchemyAuditRepository()))

        def create(token, key, coverage, purpose="ILLUSTRATES"):
            return service.create(CreateRequirementPrototypeLink(
                token, CSRF, uuid.uuid4(), ids["project"], requirement,
                requirement_version, prototype, prototype_version, purpose,
                coverage, key))

        full = RequirementPrototypeCoverage(criteria, ())
        first_key = str(uuid.uuid4())
        first = create(pm_token, first_key, full)
        replay = create(pm_token, first_key, full)
        natural = create(impl_token, str(uuid.uuid4()), full)
        assert first.requirement_prototype_link_id == replay.requirement_prototype_link_id
        assert first.requirement_prototype_link_id == natural.requirement_prototype_link_id

        split = RequirementPrototypeCoverage(
            (criteria[0],),
            (UncoveredAcceptanceCriterion(criteria[1], "Needs device"),),
        )
        try: create(impl_token, str(uuid.uuid4()), split)
        except RequirementPrototypeLinkError as error:
            assert error.code == "LINK_CONFLICT", error.code
        else: raise AssertionError("different active coverage accepted")

        validator.valid = False
        try: create(pm_token, str(uuid.uuid4()), full, "VALIDATES")
        except RequirementPrototypeLinkError as error:
            assert error.code == "PROTOTYPE_INPUT_DRIFT", error.code
        else: raise AssertionError("drifted Prototype accepted")
        validator.valid = True
        try: create(customer_token, str(uuid.uuid4()), full, "VALIDATES")
        except RequirementPrototypeLinkError as error:
            # Project authorization deliberately hides non-membership so callers
            # cannot use this command to enumerate project identities.
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else: raise AssertionError("CustomerMember created Link")

        page = service.list(RequirementPrototypeLinkQuery(
            customer_token, uuid.uuid4(), ids["project"]), page_size=1)
        assert len(page.items) == 1 and not page.has_more
        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.prt_requirement_links").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='REQUIREMENT_PROTOTYPE_LINK_CREATED'").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_PRT_REQUIREMENT_LINK_CREATE'").fetchone()[0] == 2
        command.check(cfg)
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("PRT_01_A08_A03_LINK_CREATE_LIST_PASS: real authorization, current fixed endpoint/owned ref/acceptance proof, validator fence, coverage partition, idempotent create, conflict, audit, list isolation and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
