"""Windows 11/PostgreSQL 18 proof for RequirementVersion validation."""

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
from plm_assistant.modules.audit.infrastructure.requirement_validation_source import SqlAlchemyRequirementValidationAuditSource
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.capability.infrastructure.requirement_source_proof import SqlAlchemyCapabilityRequirementSourceProof
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
    RequirementAssessmentEvidenceDraft, RequirementCapabilityAssessmentDraft,
    RequirementSourceDraft, RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionValidationError, RequirementVersionValidationService,
    ValidateRequirementVersion,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import SqlAlchemyRequirementIdentityCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_create_repository import SqlAlchemyRequirementVersionCreateRepository
from plm_assistant.modules.requirement.infrastructure.version_validation_repository import SqlAlchemyRequirementVersionValidationRepository


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, CSRF = helpers["Guard"], helpers["CSRF"]
definition = runpy.run_path(str(ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"))
rounds = runpy.run_path(str(ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"))
seed_dependencies, insert_evidence = definition["seed_dependencies"], rounds["insert_evidence"]


def expect(code: str, action) -> None:
    try:
        action()
    except RequirementVersionValidationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    database = "req01a07_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            pm = seed_user(db, "Requirement Validate PM", "NONE", pm_token)
            impl = seed_user(db, "Requirement Validate Implementer", "NONE", impl_token)
            customer = seed_user(db, "Requirement Validate Customer", "NONE", customer_token)
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (impl, "IMPLEMENTATION_MEMBER"),
                                (customer, "CUSTOMER_MANAGER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,%s)",
                    (ids["project"], actor, ids["department"], role),
                )
            project_evidence, _, _, _ = insert_evidence(db, ids)
            standard_evidence = uuid.uuid4()
            review, round_id, snapshot = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,"
                    "document_id,document_version_id,locator_type,locator_schema_version,"
                    "locator_payload,content_fingerprint,display_label,eligibility_state,"
                    "eligibility_reason,created_by) VALUES "
                    "(%s,'GLOBAL',NULL,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,"
                    "%s,'Standard evidence','ELIGIBLE','REQ-01-A07 fixture',%s)",
                    (standard_evidence, ids["template_document"], ids["template_version"],
                     b"standard-evidence".ljust(32, b"x")[:32], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
                    "subject_id,policy_code,review_state,active_round_id,lock_version,created_by) "
                    "VALUES (%s,'GLOBAL',NULL,'CAP-01',%s,'DEPLOYMENT_ALL_V1','APPROVED',NULL,2,%s)",
                    (review, ids["baseline"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,project_id,"
                    "round_no,subject_version_id,round_state,lock_version,started_by,started_at) "
                    "VALUES (%s,%s,'GLOBAL',NULL,1,%s,'APPROVED',1,%s,statement_timestamp())",
                    (round_id, review, ids["baseline_version"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,review_round_id,"
                    "scope,project_id,subject_type,subject_id,subject_version_id,content_fingerprint,"
                    "proof_schema_version,verified_at) VALUES "
                    "(%s,%s,%s,'GLOBAL',NULL,'CAP-01',%s,%s,%s,1,statement_timestamp())",
                    (snapshot, review, round_id, ids["baseline"],
                     ids["baseline_version"], b"c" * 32),
                )
                db.execute(
                    "UPDATE plm.cap_baseline_versions SET review_ref=%s,review_round_ref=%s "
                    "WHERE baseline_version_id=%s",
                    (review, round_id, ids["baseline_version"]),
                )

        runtime = create_database_runtime(url)
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
        identity = RequirementIdentityCreateService(
            **common, repository=SqlAlchemyRequirementIdentityCreateRepository(),
            audit=audit,
        )
        root = identity.create_requirement(CreateRequirementIdentity(
            pm_token, CSRF, uuid.uuid4(), ids["project"], "REQ-VALIDATE",
            str(uuid.uuid4()),
        ))
        project_sources = SqlAlchemyEvidenceRequirementSourceProof()
        capability_sources = SqlAlchemyCapabilityRequirementSourceProof()
        fixed_evidence = SqlAlchemyEvidenceFixedSourceRepository()
        creator = RequirementVersionCreateService(
            **common, repository=SqlAlchemyRequirementVersionCreateRepository(),
            audit=audit, survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=project_sources,
            capability_sources=capability_sources, fixed_evidence=fixed_evidence,
        )

        def create(*, expected: int, initial: bool, base, classification: str,
                   assessments, key: str):
            return creator.create(CreateRequirementVersion(
                impl_token, CSRF, uuid.uuid4(), ids["project"], root.requirement_id,
                expected, initial, base, None, "Validated requirement",
                "Business rationale", "PLM", "HIGH", "MEDIUM", classification,
                (RequirementSourceDraft(
                    "PROJECT_EVIDENCE", project_evidence, None,
                    (project_evidence,)),),
                (RequirementAcceptanceDraft(
                    "Observable result", "Execute acceptance test", "Project data",
                    "Windows 11", "Signed acceptance report"),),
                assessments, (), (), (), (), "Create validation fixture", key,
            ))

        standard = (RequirementCapabilityAssessmentDraft(
            ids["baseline_version"], ids["capability_item"], "DIRECT",
            "Standard capability covers requirement", "Use standard configuration",
            "HUMAN", "CONFIRMED",
            (RequirementAssessmentEvidenceDraft(standard_evidence, "STANDARD"),
             RequirementAssessmentEvidenceDraft(project_evidence, "PROJECT")),
        ),)
        first = create(expected=0, initial=True, base=None,
                       classification="STANDARD_FUNCTION", assessments=standard,
                       key=str(uuid.uuid4()))

        validator = RequirementVersionValidationService(
            **common, audit=audit, survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=project_sources,
            capability_sources=capability_sources, fixed_evidence=fixed_evidence,
            repository=SqlAlchemyRequirementVersionValidationRepository(),
            audit_source=SqlAlchemyRequirementValidationAuditSource(),
        )

        def validate(version_id, *, token=impl_token, key=None):
            return validator.validate(ValidateRequirementVersion(
                token, CSRF, uuid.uuid4(), ids["project"], root.requirement_id,
                version_id, key or str(uuid.uuid4()),
            ))

        expect("RESOURCE_NOT_FOUND", lambda: validate(
            first.requirement_version_id, token=customer_token))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: validate(first.requirement_version_id))
        guard.enabled = True
        stable_key = str(uuid.uuid4())
        passed = validate(first.requirement_version_id, key=stable_key)
        assert passed.valid and passed.issue_codes == ()
        assert validate(first.requirement_version_id, key=stable_key) == passed
        expect("CONFLICT_IDEMPOTENCY", lambda: validator.validate(
            ValidateRequirementVersion(
                impl_token, CSRF, uuid.uuid4(), ids["project"], uuid.uuid4(),
                first.requirement_version_id, stable_key,
            )))

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='A07 current-fact drift' WHERE evidence_id=%s",
                (project_evidence,),
            )
        assert validate(first.requirement_version_id, key=stable_key) == passed
        drift = validate(first.requirement_version_id)
        assert not drift.valid
        assert drift.issue_codes == ("SOURCE_UNAVAILABLE", "EVIDENCE_UNAVAILABLE")

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                "eligibility_reason='A07 restored' WHERE evidence_id=%s",
                (project_evidence,),
            )
            db.execute(
                "UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                "WHERE snapshot_id=%s", (b"x" * 32, snapshot),
            )
        capability_drift = validate(first.requirement_version_id)
        assert capability_drift.issue_codes == ("CAPABILITY_UNAVAILABLE",)

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                "WHERE snapshot_id=%s", (b"c" * 32, snapshot),
            )
        pending = create(
            expected=1, initial=False, base=first.requirement_version_id,
            classification="PENDING_CONFIRMATION", assessments=(),
            key=str(uuid.uuid4()),
        )
        pending_report = validate(pending.requirement_version_id)
        assert pending_report.issue_codes == ("PENDING_CONFIRMATION",)
        assert not pending_report.valid
        expect("RESOURCE_NOT_FOUND", lambda: validator.validate(
            ValidateRequirementVersion(
                impl_token, CSRF, uuid.uuid4(), uuid.uuid4(), root.requirement_id,
                first.requirement_version_id, str(uuid.uuid4()),
            )))

        with connect(database) as db:
            states = db.execute(
                "SELECT version_state FROM plm.req_requirement_versions "
                "WHERE requirement_id=%s ORDER BY version_no", (root.requirement_id,),
            ).fetchall()
            assert states == [("DRAFT",), ("DRAFT",)], states
            audits = db.execute(
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='REQUIREMENT_VERSION_VALIDATED'",
            ).fetchone()[0]
            receipts = db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_REQ_VERSION_VALIDATE'",
            ).fetchone()[0]
            assert audits == receipts == 4, (audits, receipts)
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print("REQ_01_A07_VERSION_VALIDATE_PASS: classification, criteria, current source/"
          "capability/evidence, immutable replay, denial, zero state transition and drift "
          "verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
