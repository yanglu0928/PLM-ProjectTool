"""Windows 11/PostgreSQL 18 proof for Link REVOKE/SUPERSEDE Owner."""

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
    RequirementPrototypeLinkError, RequirementPrototypeLinkService,
    RevokeRequirementPrototypeLink, SupersedeRequirementPrototypeLink,
    UncoveredAcceptanceCriterion,
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


class FailingReplacementRepository(SqlAlchemyRequirementPrototypeLinkRepository):
    def create_replacement(self, *_args, **_kwargs):
        raise RuntimeError("synthetic replacement insert failure")


def main() -> None:
    database = "prt01a08a04_" + uuid.uuid4().hex[:8]
    pm_token, customer_token = b"p" * 32, b"c" * 32
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
            pm = seed_user(db, "Link lifecycle PM", "NONE", pm_token)
            customer = seed_user(db, "Link lifecycle customer", "NONE", customer_token)
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (customer, "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], actor, ids["department"], role))
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,requirement_code_normalized,requirement_state,current_approved_version_ref,created_by) VALUES (%s,%s,'LINK-LIFE','LINK-LIFE','ACTIVE',%s,%s)",
                           (requirement, ids["project"], requirement_version, pm))
                db.execute("INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,project_id,version_no,version_state,statement,rationale,domain_name,priority,risk,requirement_classification,content_fingerprint,declared_source_count,declared_acceptance_count,declared_capability_count,declared_assumption_count,declared_exclusion_count,declared_dependency_count,declared_ai_task_count,review_ref,review_round_ref,created_by) VALUES (%s,%s,%s,1,'APPROVED','Statement','Rationale','PLM','HIGH','MEDIUM','STANDARD_FUNCTION',%s,1,2,0,0,0,0,0,%s,%s,%s)",
                           (requirement_version, requirement, ids["project"], b"r"*32, uuid.uuid4(), uuid.uuid4(), pm))
                for ordinal, criterion in enumerate(criteria):
                    db.execute("INSERT INTO plm.req_acceptance_criteria(acceptance_criterion_id,requirement_version_id,requirement_id,project_id,ordinal,observable_result,verification_method,required_data,required_environment,evidence_requirement) VALUES (%s,%s,%s,%s,%s,'Observed','Manual','Data','Environment','Evidence')",
                               (criterion, requirement_version, requirement, ids["project"], ordinal))
                db.execute("INSERT INTO plm.prt_prototypes(prototype_id,project_id,name,prototype_state,current_approved_version_ref,created_by) VALUES (%s,%s,'Lifecycle prototype','ACTIVE',%s,%s)",
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

        def service(repository):
            return RequirementPrototypeLinkService(
                unit_of_work=runtime.unit_of_work,
                write_access=SqlAlchemyProjectWriteAccess(),
                read_access=SqlAlchemyProjectReadAccess(), license_guard=Guard(),
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository()),
                repository=repository, version_reader=Reader(snapshot),
                current_validator=validator,
                receipts=SqlAlchemyIdempotencyReceipts(),
                audit=AuditService(SqlAlchemyAuditRepository()))

        owner = service(SqlAlchemyRequirementPrototypeLinkRepository())
        full = RequirementPrototypeCoverage(criteria, ())
        split = RequirementPrototypeCoverage(
            (criteria[0],),
            (UncoveredAcceptanceCriterion(criteria[1], "Needs device"),),
        )

        def create(purpose):
            return owner.create(CreateRequirementPrototypeLink(
                pm_token, CSRF, uuid.uuid4(), ids["project"], requirement,
                requirement_version, prototype, prototype_version, purpose,
                full, str(uuid.uuid4())))

        def supersede(link_id, coverage, key, target=owner):
            return target.supersede(SupersedeRequirementPrototypeLink(
                session_token=pm_token, csrf_token=CSRF,
                trace_id=uuid.uuid4(), project_id=ids["project"],
                requirement_prototype_link_id=link_id,
                requirement_id=requirement,
                requirement_version_id=requirement_version,
                prototype_id=prototype,
                prototype_version_id=prototype_version,
                purpose="ILLUSTRATES", coverage=coverage,
                expected_version=0, idempotency_key=key,
            ))

        original = create("ILLUSTRATES")
        try: supersede(original.requirement_prototype_link_id, full, str(uuid.uuid4()))
        except RequirementPrototypeLinkError as error:
            assert error.code == "VALIDATION_FAILED", error.code
        else: raise AssertionError("identical replacement accepted")

        validator.valid = False
        try: supersede(original.requirement_prototype_link_id, split, str(uuid.uuid4()))
        except RequirementPrototypeLinkError as error:
            assert error.code == "PROTOTYPE_INPUT_DRIFT", error.code
        else: raise AssertionError("drifted replacement accepted")
        validator.valid = True

        broken = service(FailingReplacementRepository())
        try: supersede(original.requirement_prototype_link_id, split,
                       str(uuid.uuid4()), broken)
        except RequirementPrototypeLinkError as error:
            assert error.code == "REQUIREMENT_PROTOTYPE_LINK_UNAVAILABLE", error.code
        else: raise AssertionError("replacement insert failure committed")
        with connect(database) as db:
            assert db.execute("SELECT link_state,lock_version,superseded_by_ref FROM plm.prt_requirement_links WHERE requirement_prototype_link_id=%s", (original.requirement_prototype_link_id,)).fetchone() == ("ACTIVE", 0, None)

        supersede_key = str(uuid.uuid4())
        replacement = supersede(
            original.requirement_prototype_link_id, split, supersede_key)
        replay = supersede(
            original.requirement_prototype_link_id, split, supersede_key)
        assert replay.requirement_prototype_link_id == replacement.requirement_prototype_link_id

        revoke_key = str(uuid.uuid4())
        revoke = RevokeRequirementPrototypeLink(
            pm_token, CSRF, uuid.uuid4(), ids["project"],
            replacement.requirement_prototype_link_id, 0, revoke_key,
        )
        revoked = owner.revoke(revoke)
        replayed_revoke = owner.revoke(revoke)
        assert revoked == replayed_revoke and revoked.link_state == "REVOKED"

        denied = RevokeRequirementPrototypeLink(
            customer_token, CSRF, uuid.uuid4(), ids["project"],
            replacement.requirement_prototype_link_id, 0, str(uuid.uuid4()),
        )
        try: owner.revoke(denied)
        except RequirementPrototypeLinkError as error:
            assert error.code == "RESOURCE_NOT_FOUND", error.code
        else: raise AssertionError("CustomerMember revoked Link")

        with connect(database) as db:
            rows = db.execute("SELECT requirement_prototype_link_id,link_state,lock_version,superseded_by_ref FROM plm.prt_requirement_links ORDER BY created_at,requirement_prototype_link_id").fetchall()
            assert len(rows) == 2
            old = next(row for row in rows if row[0] == original.requirement_prototype_link_id)
            new = next(row for row in rows if row[0] == replacement.requirement_prototype_link_id)
            assert old[1:] == ("SUPERSEDED", 1, replacement.requirement_prototype_link_id)
            assert new[1:] == ("REVOKED", 1, None)
            audits = dict(db.execute("SELECT action,count(*) FROM plm.aud_events WHERE action LIKE 'REQUIREMENT_PROTOTYPE_LINK_%' GROUP BY action").fetchall())
            assert audits == {
                "REQUIREMENT_PROTOTYPE_LINK_CREATED": 2,
                "REQUIREMENT_PROTOTYPE_LINK_REVOKED": 1,
                "REQUIREMENT_PROTOTYPE_LINK_SUPERSEDED": 1,
            }, audits
            receipts = dict(db.execute("SELECT operation,count(*) FROM plm.plt_idempotency_receipts WHERE operation LIKE 'V1_PRT_REQUIREMENT_LINK_%' GROUP BY operation").fetchall())
            assert receipts == {
                "V1_PRT_REQUIREMENT_LINK_CREATE": 1,
                "V1_PRT_REQUIREMENT_LINK_REVOKE": 1,
                "V1_PRT_REQUIREMENT_LINK_SUPERSEDE": 1,
            }, receipts
        command.check(cfg)
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
    print("PRT_01_A08_A04_LINK_LIFECYCLE_PASS: same-identity/purpose supersede, current proof, ordered replacement, deferred closure, revoke, durable replay, audit and rollback verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
