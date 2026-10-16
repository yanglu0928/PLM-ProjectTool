"""Windows 11/PostgreSQL 18 proof for DRAFT SurveyVersion creation."""

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
    SurveyVersionCreateError, SurveyVersionCreateService,
)
from plm_assistant.modules.survey.infrastructure.version_create_repository import SqlAlchemySurveyVersionCreateRepository


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(ROOT / "validation/sur-01-a02-definition-schema/verify.py"))
helpers = runpy.run_path(str(ROOT / "validation/ai-02-a02-model-create/verify.py"))
connect, seed_dependencies = schema["connect"], schema["seed_dependencies"]
seed_user, Guard, FailedAudit, CSRF = (helpers["seed_user"], helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"])


def expect(code, action):
    try: action()
    except SurveyVersionCreateError as error: assert error.code == code, (error.code, code)
    else: raise AssertionError(code)


def questions(ids):
    return (
        SurveyQuestionDraft(uuid.uuid4(), "Scope", "Confirm scope", "Fix scope", "TEXT", {}, True, None, "Confirmed scope", False, (),
            (SurveySourceDraft("HANDOVER_ITEM", ids["handover_item_row"], ids["analysis_version"], ids["analysis"]),)),
        SurveyQuestionDraft(uuid.uuid4(), "Capability", "Is capability used?", "Map standard", "SINGLE_CHOICE", {}, True, None, "Choice", False,
            (SurveyOptionDraft("YES", "Yes"), SurveyOptionDraft("NO", "No")),
            (SurveySourceDraft("CAPABILITY_ITEM", capability_item_row_id=ids["capability_item_row"], capability_baseline_version_id=ids["baseline_version"], capability_baseline_id=ids["baseline"]),)),
        SurveyQuestionDraft(uuid.uuid4(), "Template", "Template prompt", "Use structure", "TEXT", {}, False, None, "Text", False, (),
            (SurveySourceDraft("TEMPLATE_DOCUMENT_VERSION", template_document_version_id=ids["template_version"], template_document_id=ids["template_document"]),)),
        SurveyQuestionDraft(uuid.uuid4(), "Manual", "Facilitator prompt", "Clarify", "TEXT", {}, False, None, "Text", True, (),
            (SurveySourceDraft("MANUAL", manual_source_note="Facilitator-added question"),)),
    )


def main():
    database = "sur01a03p02a03_" + uuid.uuid4().hex[:6]
    token = b"p" * 32
    with connect("postgres") as admin: admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=database)
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = seed_dependencies(db)
            pm = seed_user(db, "Survey Version PM", "NONE", token)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (ids["project"], pm, ids["department"]))
            survey = db.execute("INSERT INTO plm.srv_surveys(project_id,name,created_by) VALUES (%s,'Business discovery',%s) RETURNING survey_id", (ids["project"], pm)).fetchone()[0]
        runtime = create_database_runtime(url)
        try:
            guard = Guard()
            common = dict(unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository()),
                handover_sources=SqlAlchemyHandoverSurveySourceProof(), capability_sources=SqlAlchemyCapabilitySurveySourceProof(),
                template_sources=SqlAlchemySurveyTemplateProof(), departments=SqlAlchemySurveyTargetDepartmentProof(),
                repository=SqlAlchemySurveyVersionCreateRepository(), receipts=SqlAlchemyIdempotencyReceipts(),
                clock=lambda: datetime.now(timezone.utc))
            def service(audit=None): return SurveyVersionCreateService(**common, audit=audit or AuditService(SqlAlchemyAuditRepository()))
            base_questions = questions(ids)
            def create(expected=0, key=None, q=base_questions, target=None):
                return (target or service()).create(CreateSurveyVersion(token, CSRF, uuid.uuid4(), ids["project"], survey, expected, q, (ids["department"],), key or str(uuid.uuid4())))
            guard.enabled = False; expect("LICENSE_OPERATION_DENIED", create); guard.enabled = True
            key = str(uuid.uuid4()); first = create(key=key); assert first == create(key=key)
            expect("CONFLICT_IDEMPOTENCY", lambda: create(key=key, q=questions(ids)))
            second = create(expected=1); assert second.version_no == 2 and second.supersedes_version_ref == first.survey_version_id
            expect("CONFLICT_VERSION", lambda: create(expected=1))
            rollback_key = str(uuid.uuid4())
            expect("SURVEY_UNAVAILABLE", lambda: create(expected=2, key=rollback_key, target=service(FailedAudit())))
            recovered = create(expected=2, key=rollback_key); assert recovered.version_no == 3
            with connect(database) as db:
                counts = db.execute("SELECT (SELECT count(*) FROM plm.srv_survey_versions),(SELECT count(*) FROM plm.srv_questions),(SELECT count(*) FROM plm.srv_question_options),(SELECT count(*) FROM plm.srv_question_source_refs),(SELECT count(*) FROM plm.srv_target_departments)").fetchone()
                assert counts == (3, 12, 6, 12, 3), counts
                assert db.execute("SELECT lock_version FROM plm.srv_surveys WHERE survey_id=%s", (survey,)).fetchone()[0] == 3
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SURVEY_VERSION_CREATED'").fetchone()[0] == 3
            print("SUR_01_A03_P02_A03_VERSION_CREATE_PASS: typed source proofs, canonical immutable versions, supersede chain, replay/conflict, Audit rollback and six-table atomicity verified on PostgreSQL 18")
        finally: runtime.dispose()
    finally:
        with connect("postgres") as admin: admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


if __name__ == "__main__": main()
