"""Windows 11/PostgreSQL 18 proof for Requirement Review schema."""

from __future__ import annotations

import runpy
import uuid
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
from plm_assistant.modules.requirement.application.create_identity import CreateRequirementIdentity, RequirementIdentityCreateService
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, RequirementAcceptanceDraft,
    RequirementSourceDraft, RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
evidence_helpers = runpy.run_path(str(ROOT / "validation" / "wfl-02-a01-p03-history-schema" / "verify.py"))
seed_evidence = evidence_helpers["seed_evidence"]
PREVIOUS = "20261007_0119"


def rejected(action, message: str) -> None:
    try:
        action()
    except psycopg.Error as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + message)


def seed_review(db, *, project, requirement, version, actor):
    review, round_id = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
            "subject_id,policy_code,review_state,active_round_id,lock_version,created_by) "
            "VALUES (%s,'PROJECT',%s,'REQ-03',%s,'REQUIREMENT_ALL_V1','IN_REVIEW',%s,1,%s)",
            (review, project, requirement, round_id, actor),
        )
        db.execute(
            "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,project_id,"
            "round_no,subject_version_id,round_state,lock_version,started_by,started_at) "
            "VALUES (%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',0,%s,statement_timestamp())",
            (round_id, review, project, version, actor),
        )
    return review, round_id


def set_review_terminal(db, review, round_id, state):
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.rvw_reviews SET review_state=%s,active_round_id=NULL,lock_version=2 "
            "WHERE review_id=%s", (state, review),
        )
        db.execute(
            "UPDATE plm.rvw_review_rounds SET round_state=%s,lock_version=1 "
            "WHERE review_round_id=%s",
            (state, round_id),
        )


def main() -> None:
    database = "req01a08p01_" + uuid.uuid4().hex[:8]
    pm_token, impl_token = b"p" * 32, b"i" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
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
        with connect(database) as db:
            pm = seed_user(db, "Requirement Review PM", "NONE", pm_token)
            impl = seed_user(db, "Requirement Review Implementer", "NONE", impl_token)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('REQRVW','reqrvw','Requirement Review',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (impl, "IMPLEMENTATION_MEMBER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,%s)", (project, actor, department, role),
                )
            evidence = seed_evidence(db, project, pm)

        guard = Guard()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        common = dict(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )
        audit = AuditService(SqlAlchemyAuditRepository())
        root = RequirementIdentityCreateService(
            **common, repository=SqlAlchemyRequirementIdentityCreateRepository(),
            audit=audit,
        ).create_requirement(CreateRequirementIdentity(
            pm_token, CSRF, uuid.uuid4(), project, "REQ-REVIEW",
            str(uuid.uuid4()),
        ))
        creator = RequirementVersionCreateService(
            **common, repository=SqlAlchemyRequirementVersionCreateRepository(),
            audit=audit, survey_sources=object(), handover_sources=object(),
            human_decisions=object(),
            project_evidence=SqlAlchemyEvidenceRequirementSourceProof(),
            capability_sources=object(),
            fixed_evidence=SqlAlchemyEvidenceFixedSourceRepository(),
        )

        def create(expected, initial, base):
            return creator.create(CreateRequirementVersion(
                impl_token, CSRF, uuid.uuid4(), project, root.requirement_id,
                expected, initial, base, None, "Review lifecycle requirement",
                "Business rationale", "PLM", "HIGH", "MEDIUM",
                "PENDING_CONFIRMATION",
                (RequirementSourceDraft(
                    "PROJECT_EVIDENCE", evidence, None, (evidence,)),),
                (RequirementAcceptanceDraft(
                    "Observable result", "Execute test", "Project data",
                    "Windows 11", "Signed report"),),
                (), (), (), (), (), "Create Review fixture", str(uuid.uuid4()),
            ))

        first = create(0, True, None)
        with connect(database) as db:
            review, round_id = seed_review(
                db, project=project, requirement=root.requirement_id,
                version=first.requirement_version_id, actor=pm,
            )
            with db.transaction():
                db.execute(
                    "UPDATE plm.req_requirement_versions SET version_state='IN_REVIEW',"
                    "review_ref=%s,review_round_ref=%s WHERE requirement_version_id=%s",
                    (review, round_id, first.requirement_version_id),
                )
                db.execute(
                    "UPDATE plm.req_requirements SET updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                    "WHERE requirement_id=%s", (pm, root.requirement_id),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_review_state_results("
                    "requirement_version_id,requirement_id,project_id,review_id,review_round_id,"
                    "event_type,previous_approved_version_ref,current_approved_version_ref,"
                    "actor_id,expected_lock_version,lock_version) "
                    "VALUES (%s,%s,%s,%s,%s,'START',NULL,NULL,%s,1,2)",
                    (first.requirement_version_id, root.requirement_id, project,
                     review, round_id, pm),
                )
            rejected(lambda: _root_bump_without_result(db, root.requirement_id, pm),
                     "Requirement mutation has no immutable result")
            set_review_terminal(db, review, round_id, "RETURNED")
            rejected(lambda: _terminal_without_result(
                db, root.requirement_id, first.requirement_version_id, pm),
                "RequirementVersion Review transition has no immutable result")
            with db.transaction():
                db.execute(
                    "UPDATE plm.req_requirement_versions SET version_state='RETURNED' "
                    "WHERE requirement_version_id=%s", (first.requirement_version_id,),
                )
                db.execute(
                    "UPDATE plm.req_requirements SET updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                    "WHERE requirement_id=%s", (pm, root.requirement_id),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_review_state_results("
                    "requirement_version_id,requirement_id,project_id,review_id,review_round_id,"
                    "event_type,previous_approved_version_ref,current_approved_version_ref,"
                    "actor_id,expected_lock_version,lock_version) "
                    "VALUES (%s,%s,%s,%s,%s,'RETURNED',NULL,NULL,%s,2,3)",
                    (first.requirement_version_id, root.requirement_id, project,
                     review, round_id, pm),
                )

        second = create(3, False, first.requirement_version_id)
        with connect(database) as db:
            review2, round2 = seed_review(
                db, project=project, requirement=root.requirement_id,
                version=second.requirement_version_id, actor=pm,
            )
            with db.transaction():
                db.execute(
                    "UPDATE plm.req_requirement_versions SET version_state='IN_REVIEW',"
                    "review_ref=%s,review_round_ref=%s WHERE requirement_version_id=%s",
                    (review2, round2, second.requirement_version_id),
                )
                db.execute(
                    "UPDATE plm.req_requirements SET updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                    "WHERE requirement_id=%s", (pm, root.requirement_id),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_review_state_results("
                    "requirement_version_id,requirement_id,project_id,review_id,review_round_id,"
                    "event_type,actor_id,expected_lock_version,lock_version) "
                    "VALUES (%s,%s,%s,%s,%s,'START',%s,4,5)",
                    (second.requirement_version_id, root.requirement_id, project,
                     review2, round2, pm),
                )
            set_review_terminal(db, review2, round2, "APPROVED")
            with db.transaction():
                db.execute(
                    "UPDATE plm.req_requirement_versions SET version_state='APPROVED' "
                    "WHERE requirement_version_id=%s", (second.requirement_version_id,),
                )
                db.execute(
                    "UPDATE plm.req_requirements SET current_approved_version_ref=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=lock_version+1 "
                    "WHERE requirement_id=%s",
                    (second.requirement_version_id, pm, root.requirement_id),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_review_state_results("
                    "requirement_version_id,requirement_id,project_id,review_id,review_round_id,"
                    "event_type,previous_approved_version_ref,current_approved_version_ref,"
                    "actor_id,expected_lock_version,lock_version) "
                    "VALUES (%s,%s,%s,%s,%s,'APPROVED',NULL,%s,%s,5,6)",
                    (second.requirement_version_id, root.requirement_id, project,
                     review2, round2, second.requirement_version_id, pm),
                )
            row = db.execute(
                "SELECT current_approved_version_ref,lock_version FROM plm.req_requirements "
                "WHERE requirement_id=%s", (root.requirement_id,),
            ).fetchone()
            assert row == (second.requirement_version_id, 6), row
            rejected(lambda: _truncate_results(db),
                     "Requirement Review result history cannot be truncated")
        command.check(cfg)
        try:
            command.downgrade(cfg, PREVIOUS)
        except RuntimeError as error:
            assert "Review history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Requirement Review history was downgraded")
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print("REQ_01_A08_A02_P01_REVIEW_SCHEMA_PASS: migration, immutable root closure, "
          "start, returned, approved, direct-write/truncate refusal, downgrade and drift "
          "verified on Windows 11/PostgreSQL 18")


def _root_bump_without_result(db, requirement, actor):
    with db.transaction():
        db.execute(
            "UPDATE plm.req_requirements SET updated_by=%s,updated_at=statement_timestamp(),"
            "lock_version=lock_version+1 WHERE requirement_id=%s", (actor, requirement),
        )


def _terminal_without_result(db, requirement, version, actor):
    with db.transaction():
        db.execute(
            "UPDATE plm.req_requirement_versions SET version_state='RETURNED' "
            "WHERE requirement_version_id=%s", (version,),
        )
        db.execute(
            "UPDATE plm.req_requirements SET updated_by=%s,updated_at=statement_timestamp(),"
            "lock_version=lock_version+1 WHERE requirement_id=%s", (actor, requirement),
        )


def _truncate_results(db):
    with db.transaction():
        db.execute("TRUNCATE plm.req_requirement_review_state_results")


if __name__ == "__main__":
    main()
