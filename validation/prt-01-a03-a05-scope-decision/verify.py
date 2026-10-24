"""Windows 11/PostgreSQL 18 proof for Prototype NOT_REQUIRED decisions."""

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
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.prototype.application.create_identity import (
    CreatePrototypeIdentity, PrototypeIdentityCreateService,
)
from plm_assistant.modules.prototype.application.mark_not_required import (
    MarkPrototypeNotRequired, PrototypeScopeDecisionError,
    PrototypeScopeDecisionService,
)
from plm_assistant.modules.prototype.application.mutate_prototype import (
    ArchivePrototypeIdentity, PrototypeMutationService,
)
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import (
    SqlAlchemyPrototypeIdentityCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.prototype_mutation_repository import (
    SqlAlchemyPrototypeMutationRepository,
)
from plm_assistant.modules.prototype.infrastructure.scope_decision_repository import (
    SqlAlchemyPrototypeScopeDecisionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]
PREVIOUS = "20261008_0125"


def expect(code: str, action) -> None:
    try:
        action()
    except PrototypeScopeDecisionError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def decision_fingerprint(project, prototype, expected_version, refs, reason, impact):
    return canonical_payload_fingerprint({
        "project_id": str(project), "prototype_id": str(prototype),
        "expected_version": expected_version, "decision_type": "NOT_REQUIRED",
        "reason": reason, "impact": impact,
        "affected_requirement_version_refs": [str(item) for item in refs],
    })


def seed_requirement_scope(db, project, actor):
    pairs = sorted(((uuid.uuid4(), uuid.uuid4()), (uuid.uuid4(), uuid.uuid4())),
                   key=lambda pair: str(pair[1]))
    stale_requirement, stale_version = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        for index, (requirement_id, version_id) in enumerate(pairs, 1):
            db.execute(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
                "requirement_code_normalized,requirement_state,current_approved_version_ref,"
                "created_by,lock_version) VALUES (%s,%s,%s,%s,'ACTIVE',%s,%s,2)",
                (requirement_id, project, f"PRT-SCOPE-{index}",
                 f"PRT-SCOPE-{index}", version_id, actor),
            )
            db.execute(
                "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
                "requirement_id,project_id,version_no,version_state,title,statement,rationale,"
                "domain_name,priority,risk,requirement_classification,content_fingerprint,"
                "declared_source_count,declared_acceptance_count,declared_capability_count,"
                "declared_assumption_count,declared_exclusion_count,declared_dependency_count,"
                "declared_ai_task_count,created_by) VALUES (%s,%s,%s,1,'APPROVED',%s,"
                "'Observable statement','Business rationale','PLM','HIGH','MEDIUM',"
                "'STANDARD_FUNCTION',%s,1,1,1,0,0,0,0,%s)",
                (version_id, requirement_id, project, f"Scope {index}",
                 version_id.bytes + version_id.bytes, actor),
            )
        db.execute(
            "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
            "requirement_code_normalized,requirement_state,current_approved_version_ref,"
            "created_by,lock_version) VALUES (%s,%s,'PRT-STALE','PRT-STALE','ACTIVE',NULL,%s,0)",
            (stale_requirement, project, actor),
        )
        db.execute(
            "INSERT INTO plm.req_requirement_versions(requirement_version_id,requirement_id,"
            "project_id,version_no,version_state,title,statement,rationale,domain_name,priority,"
            "risk,requirement_classification,content_fingerprint,declared_source_count,"
            "declared_acceptance_count,declared_capability_count,declared_assumption_count,"
            "declared_exclusion_count,declared_dependency_count,declared_ai_task_count,created_by) "
            "VALUES (%s,%s,%s,1,'DRAFT','Stale','Statement','Rationale','PLM','HIGH','MEDIUM',"
            "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)",
            (stale_version, stale_requirement, project,
             stale_version.bytes + stale_version.bytes, actor),
        )
    return tuple(version for _, version in pairs), stale_version


def seed_scope_review(db, project, actor, prototype, fingerprint):
    review, round_id, snapshot = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,subject_id,"
            "policy_code,review_state,created_by) VALUES (%s,'PROJECT',%s,"
            "'PRT_SCOPE_DECISION',%s,'PROTOTYPE_SCOPE_DECISION_V1','APPROVED',%s)",
            (review, project, prototype, actor),
        )
        db.execute(
            "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,project_id,"
            "round_no,subject_version_id,round_state,started_by,started_at) "
            "VALUES (%s,%s,'PROJECT',%s,1,%s,'APPROVED',%s,%s)",
            (round_id, review, project, prototype, actor, now),
        )
        db.execute(
            "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,review_round_id,scope,"
            "project_id,subject_type,subject_id,subject_version_id,content_fingerprint,"
            "proof_schema_version,verified_at) VALUES (%s,%s,%s,'PROJECT',%s,"
            "'PRT_SCOPE_DECISION',%s,%s,%s,1,%s)",
            (snapshot, review, round_id, project, prototype, prototype,
             fingerprint, now),
        )
    return review, round_id


def main() -> None:
    database = "prt01a03a05_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        runtime = create_database_runtime(url)
        with connect(database) as db:
            pm = seed_user(db, "Scope decision PM", "NONE", pm_token)
            impl = seed_user(db, "Scope decision IM", "NONE", impl_token)
            customer = seed_user(db, "Scope decision Customer", "NONE", customer_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PRTM03','prtm03','Prototype scope decision',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in (
                (pm, "PROJECT_MANAGER"), (impl, "IMPLEMENTATION_MEMBER"),
                (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                    "project_role) VALUES (%s,%s,%s,%s)",
                    (project, actor, department, role),
                )
            refs, stale_ref = seed_requirement_scope(db, project, pm)

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        base = dict(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )
        creator = PrototypeIdentityCreateService(
            **base, repository=SqlAlchemyPrototypeIdentityCreateRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        prototype = creator.create_prototype(CreatePrototypeIdentity(
            pm_token, CSRF, uuid.uuid4(), project, "No prototype", str(uuid.uuid4()),
        ))
        no_review = creator.create_prototype(CreatePrototypeIdentity(
            pm_token, CSRF, uuid.uuid4(), project, "No review path", str(uuid.uuid4()),
        ))
        closure_probe = creator.create_prototype(CreatePrototypeIdentity(
            pm_token, CSRF, uuid.uuid4(), project, "Closure probe", str(uuid.uuid4()),
        ))
        reason, impact = "No interactive flow", "Use standard forms"
        fingerprint = decision_fingerprint(
            project, prototype.prototype_id, 0, refs, reason, impact,
        )
        with connect(database) as db:
            review, round_id = seed_scope_review(
                db, project, pm, prototype.prototype_id, fingerprint,
            )

        def service(audit=None):
            return PrototypeScopeDecisionService(
                **base, repository=SqlAlchemyPrototypeScopeDecisionRepository(),
                audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        def decide(target_id, *, expected=0, values=refs, token=customer_token,
                   key=None, review_pair=(None, None), target=None):
            return (target or service()).mark_not_required(MarkPrototypeNotRequired(
                token, CSRF, uuid.uuid4(), project, target_id, expected,
                tuple(values), reason, impact, review_pair[0], review_pair[1],
                key or str(uuid.uuid4()),
            ))

        expect("RESOURCE_NOT_FOUND", lambda: decide(prototype.prototype_id, token=impl_token))
        expect(
            "PROTOTYPE_REQUIREMENT_NOT_APPROVED",
            lambda: decide(prototype.prototype_id, values=(stale_ref,), token=pm_token),
        )
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: decide(prototype.prototype_id))
        guard.enabled = True
        expect(
            "PROTOTYPE_UNAVAILABLE",
            lambda: decide(
                prototype.prototype_id, review_pair=(review, round_id),
                target=service(FailedAudit()),
            ),
        )

        decision_key = str(uuid.uuid4())
        decided = decide(
            prototype.prototype_id, key=decision_key,
            review_pair=(review, round_id),
        )
        assert decided.prototype_state == "NOT_REQUIRED" and decided.etag == '"v1"'
        assert decided.confirmed_by == customer and decided.review_id == review
        assert decided.affected_requirement_version_refs == refs
        assert decide(
            prototype.prototype_id, key=decision_key,
            review_pair=(review, round_id),
        ) == decided
        expect(
            "CONFLICT_IDEMPOTENCY",
            lambda: decide(prototype.prototype_id, expected=1, key=decision_key,
                           review_pair=(review, round_id)),
        )
        plain = decide(no_review.prototype_id, token=pm_token)
        assert plain.review_id is None and plain.confirmed_by == pm

        probe_fingerprint = decision_fingerprint(
            project, closure_probe.prototype_id, 0, refs, reason, impact,
        )
        with connect(database) as db:
            try:
                with db.transaction():
                    decision_id = uuid.uuid4()
                    db.execute(
                        "UPDATE plm.prt_prototypes SET prototype_state='NOT_REQUIRED',"
                        "updated_by=%s,updated_at=statement_timestamp(),lock_version=1 "
                        "WHERE prototype_id=%s", (pm, closure_probe.prototype_id),
                    )
                    db.execute(
                        "INSERT INTO plm.prt_scope_decisions(scope_decision_id,prototype_id,"
                        "project_id,decision_type,reason,impact,decision_fingerprint,confirmed_by,"
                        "before_version,after_version) VALUES (%s,%s,%s,'NOT_REQUIRED',%s,%s,%s,%s,0,1)",
                        (decision_id, closure_probe.prototype_id, project, reason,
                         impact, probe_fingerprint, pm),
                    )
                    for ordinal, version_id in enumerate(refs, 1):
                        requirement_id = db.execute(
                            "SELECT requirement_id FROM plm.req_requirement_versions "
                            "WHERE requirement_version_id=%s", (version_id,),
                        ).fetchone()[0]
                        db.execute(
                            "INSERT INTO plm.prt_scope_decision_requirement_refs("
                            "scope_decision_id,prototype_id,project_id,requirement_id,"
                            "requirement_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,%s)",
                            (decision_id, closure_probe.prototype_id, project,
                             requirement_id, version_id, ordinal),
                        )
            except Exception as error:
                assert (
                    "Prototype mutation has no immutable result" in str(error)
                    or "Prototype scope decision has no complete immutable result" in str(error)
                ), str(error)
            else:
                raise AssertionError("unclosed NOT_REQUIRED decision committed")

        archive_service = PrototypeMutationService(
            **base, repository=SqlAlchemyPrototypeMutationRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        archived = archive_service.archive(ArchivePrototypeIdentity(
            pm_token, CSRF, uuid.uuid4(), project, prototype.prototype_id,
            1, str(uuid.uuid4()),
        ))
        assert archived.prototype_state == "ARCHIVED" and archived.etag == '"v2"'
        assert decide(
            prototype.prototype_id, key=decision_key,
            review_pair=(review, round_id),
        ) == decided

        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.prt_scope_decisions").fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.prt_scope_decision_requirement_refs"
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.prt_scope_decision_results"
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_PRT_MARK_NOT_REQUIRED'"
            ).fetchone()[0] == 2
            db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (customer,))
        expect(
            "AUTH_ACCESS_DENIED",
            lambda: decide(
                prototype.prototype_id, key=decision_key,
                review_pair=(review, round_id),
            ),
        )
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Prototype scope decision history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0126 accepted scope decision history")
        print(
            "PRT_01_A03_A05_SCOPE_DECISION_PASS: current Approved RequirementVersion "
            "scope, optional exact Review, PM/Customer decision, replay, Audit rollback, "
            "atomic closure, archive retention and history refusal verified on PostgreSQL 18"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
