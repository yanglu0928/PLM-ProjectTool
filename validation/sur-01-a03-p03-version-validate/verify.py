"""Windows 11/PostgreSQL 18 proof for SurveyVersion validation reports."""

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
from plm_assistant.modules.audit.infrastructure.survey_validation_source import SqlAlchemySurveyValidationAuditSource
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.capability.infrastructure.survey_source_proof import SqlAlchemyCapabilitySurveySourceProof
from plm_assistant.modules.document.infrastructure.survey_template_proof import SqlAlchemySurveyTemplateProof
from plm_assistant.modules.handover.infrastructure.survey_source_proof import SqlAlchemyHandoverSurveySourceProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.survey_source_proof import SqlAlchemySurveyTargetDepartmentProof
from plm_assistant.modules.survey.application.create_version import (
    CreateSurveyVersion, SurveyOptionDraft, SurveyQuestionDraft, SurveySourceDraft,
    SurveyVersionCreateService,
)
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionValidationError, SurveyVersionValidationService,
    ValidateSurveyVersion,
)
from plm_assistant.modules.survey.infrastructure.version_create_repository import SqlAlchemySurveyVersionCreateRepository
from plm_assistant.modules.survey.infrastructure.version_validation_repository import SqlAlchemySurveyVersionValidationRepository


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_dependencies = schema["connect"], schema["seed_dependencies"]
seed_user, Guard, FailedAudit, CSRF = (
    helpers["seed_user"], helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"],
)


def expect(code, action):
    try:
        action()
    except SurveyVersionValidationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(code)


def valid_questions(ids):
    choice_id = uuid.uuid4()
    choice = SurveyQuestionDraft(
        choice_id, "Scope", "Is the scope confirmed?", "Confirm scope",
        "SINGLE_CHOICE", {}, True, None, "Decision", False,
        (SurveyOptionDraft("YES", "Yes"), SurveyOptionDraft("NO", "No")),
        (
            SurveySourceDraft("HANDOVER_ITEM", ids["handover_item_row"],
                              ids["analysis_version"], ids["analysis"]),
            SurveySourceDraft("CAPABILITY_ITEM",
                              capability_item_row_id=ids["capability_item_row"],
                              capability_baseline_version_id=ids["baseline_version"],
                              capability_baseline_id=ids["baseline"]),
            SurveySourceDraft("TEMPLATE_DOCUMENT_VERSION",
                              template_document_version_id=ids["template_version"],
                              template_document_id=ids["template_document"]),
            SurveySourceDraft("MANUAL", manual_source_note="Facilitator-added"),
        ),
    )
    detail = SurveyQuestionDraft(
        uuid.uuid4(), "Detail", "Describe the confirmed scope", "Capture detail",
        "TEXT", {"min_length": 1, "max_length": 2000}, True,
        {"question_ref": str(choice_id), "operator": "EQUALS", "value": "YES"},
        "Scope statement", True, (),
        (SurveySourceDraft("MANUAL", manual_source_note="Facilitator follow-up"),),
    )
    return choice, detail


def invalid_questions():
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    first = SurveyQuestionDraft(
        first_id, "Invalid", "First", "First objective", "TEXT",
        {"min_length": 10, "max_length": 1}, True,
        {"question_ref": str(second_id), "operator": "ANSWERED"},
        "First output", False, (),
        (SurveySourceDraft("MANUAL", manual_source_note="Manual first"),),
    )
    second = SurveyQuestionDraft(
        second_id, "Cycle", "Second", "Second objective", "TEXT", {}, True,
        {"question_ref": str(first_id), "operator": "ANSWERED"},
        "Second output", False, (),
        (SurveySourceDraft("MANUAL", manual_source_note="Manual second"),),
    )
    return first, second


def main():
    database = "sur01a03p03_" + uuid.uuid4().hex[:6]
    token = b"v" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = seed_dependencies(db)
            actor = seed_user(db, "Survey validator", "NONE", token)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                       (ids["project"], actor, ids["department"]))
            survey = db.execute("INSERT INTO plm.srv_surveys(project_id,name,created_by) VALUES (%s,'Validation survey',%s) RETURNING survey_id",
                                (ids["project"], actor)).fetchone()[0]
        runtime = create_database_runtime(url)
        try:
            guard = Guard()
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            )
            common = dict(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization,
                handover_sources=SqlAlchemyHandoverSurveySourceProof(),
                capability_sources=SqlAlchemyCapabilitySurveySourceProof(),
                template_sources=SqlAlchemySurveyTemplateProof(),
                departments=SqlAlchemySurveyTargetDepartmentProof(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                audit=AuditService(SqlAlchemyAuditRepository()),
                clock=lambda: datetime.now(timezone.utc),
            )
            creator = SurveyVersionCreateService(
                **common, repository=SqlAlchemySurveyVersionCreateRepository(),
            )
            first = creator.create(CreateSurveyVersion(
                token, CSRF, uuid.uuid4(), ids["project"], survey, 0,
                valid_questions(ids), (ids["department"],), str(uuid.uuid4()),
            ))
            second = creator.create(CreateSurveyVersion(
                token, CSRF, uuid.uuid4(), ids["project"], survey, 1,
                invalid_questions(), (ids["department"],), str(uuid.uuid4()),
            ))

            def validator(audit=None):
                return SurveyVersionValidationService(
                    **(common | {"audit": audit or common["audit"]}),
                    repository=SqlAlchemySurveyVersionValidationRepository(),
                    audit_source=SqlAlchemySurveyValidationAuditSource(),
                )

            def validate(version_id, key=None, target=None):
                return (target or validator()).validate(ValidateSurveyVersion(
                    token, CSRF, uuid.uuid4(), ids["project"], survey,
                    version_id, key or str(uuid.uuid4()),
                ))

            guard.enabled = False
            expect("LICENSE_OPERATION_DENIED", lambda: validate(first.survey_version_id))
            guard.enabled = True
            key = str(uuid.uuid4())
            passed = validate(first.survey_version_id, key)
            assert passed.valid and passed.issue_codes == ()
            assert (passed.question_count, passed.option_count, passed.source_count,
                    passed.target_department_count, passed.conditional_question_count) == (2, 2, 5, 1, 1)

            with connect(database) as db:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute("UPDATE plm.doc_document_versions SET availability_state='RESTRICTED' WHERE document_version_id=%s",
                               (ids["template_version"],))
            replay = validate(first.survey_version_id, key)
            assert replay == passed
            unavailable = validate(first.survey_version_id)
            assert not unavailable.valid and unavailable.issue_codes == ("SOURCE_UNAVAILABLE",)
            expect("CONFLICT_IDEMPOTENCY", lambda: validate(second.survey_version_id, key))

            invalid = validate(second.survey_version_id)
            assert not invalid.valid
            assert invalid.issue_codes == (
                "QUESTION_RULE_INVALID", "CONDITION_REFERENCE_INVALID", "CONDITION_CYCLE",
            ), invalid.issue_codes

            with connect(database) as db:
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute("UPDATE plm.doc_document_versions SET availability_state='AVAILABLE' WHERE document_version_id=%s",
                               (ids["template_version"],))
            rollback_key = str(uuid.uuid4())
            expect("SURVEY_UNAVAILABLE", lambda: validate(
                first.survey_version_id, rollback_key,
                validator(AuditService(FailedAudit())),
            ))
            recovered = validate(first.survey_version_id, rollback_key)
            assert recovered.valid
            with connect(database) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SURVEY_VERSION_VALIDATED'").fetchone()[0] == 4
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_SURVEY_VERSION_VALIDATE'").fetchone()[0] == 4
            print("SUR_01_A03_P03_VERSION_VALIDATE_PASS: bounded condition graph, answer rules, current sources, complete reports, replay/conflict and Audit rollback verified on PostgreSQL 18")
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
