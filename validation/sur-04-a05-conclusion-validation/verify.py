"""Windows 11/PostgreSQL 18 proof for SurveyConclusion current validation."""

from __future__ import annotations

import importlib.util
import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.infrastructure.survey_conclusion_task import (
    SqlAlchemySurveyConclusionAITaskProof,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.audit.infrastructure.conclusion_validation_source import (
    SqlAlchemyConclusionValidationAuditSource,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.infrastructure.survey_conclusion_issue import (
    SqlAlchemySurveyConclusionIssueProof,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    SurveyConclusionProjectRecordProofService,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionEvidenceInput, ConclusionOpenIssueInput, CreateSurveyConclusion,
    DepartmentConclusionInput, ModuleConclusionInput,
    SurveyConclusionCreateService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionValidationError, SurveyConclusionValidationService,
    ValidateSurveyConclusion,
)
from plm_assistant.modules.survey.infrastructure.conclusion_repository import (
    SqlAlchemySurveyConclusionRepository,
)
from plm_assistant.modules.survey.infrastructure.conclusion_response_source import (
    SqlAlchemyConclusionResponseProof,
)
from plm_assistant.modules.survey.infrastructure.conclusion_validation_repository import (
    SqlAlchemySurveyConclusionValidationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a04 = load(
    ROOT / "validation" / "sur-04-a04-conclusion-create-read" / "verify.py",
    "sur04a05_owner_fixture",
)
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
schema, definition, round_fixture = a04.schema, a04.definition, a04.round_fixture
seed_user = auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


def expect(code: str, action) -> None:
    try:
        action()
    except SurveyConclusionValidationError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected validation failure: " + code)


def main() -> None:
    database = "sur04a05_" + uuid.uuid4().hex[:8]
    pm_token, customer_token = b"p" * 32, b"c" * 32
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username=USER, host=HOST, port=PORT,
            database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        with schema.connect(database) as db:
            ids = definition.seed_dependencies(db)
            pm = seed_user(db, "Conclusion validation PM", "NONE", pm_token)
            customer = seed_user(
                db, "Conclusion validation customer", "NONE", customer_token,
            )
            for actor, role in (
                (pm, "PROJECT_MANAGER"), (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,"
                    "department_id,project_role) VALUES (%s,%s,%s,%s)",
                    (ids["project"], actor, ids["department"], role),
                )
            survey, version = definition.insert_valid(
                db, ids, name="Conclusion validation survey",
            )
            round_fixture.approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,created_by) VALUES (%s,%s,%s,1,%s) "
                "RETURNING survey_round_id",
                (survey, version, ids["project"], pm),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s", (pm, pm, round_id),
            )
            assignment = db.execute(
                "INSERT INTO plm.srv_assignments(survey_round_id,survey_id,"
                "survey_version_id,project_id,department_id,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING survey_assignment_id",
                (round_id, survey, version, ids["project"], ids["department"], pm),
            ).fetchone()[0]
            question = db.execute(
                "SELECT question_row_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,),
            ).fetchone()[0]
            with db.transaction():
                response = db.execute(
                    "INSERT INTO plm.srv_responses(survey_assignment_id,"
                    "survey_round_id,survey_id,survey_version_id,project_id,"
                    "question_row_id,response_source,recorded_by,recorded_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,"
                    "statement_timestamp()) RETURNING survey_response_id",
                    (assignment, round_id, survey, version, ids["project"],
                     question, pm),
                ).fetchone()[0]
                answer = db.execute(
                    "INSERT INTO plm.srv_answers(survey_response_id,"
                    "survey_assignment_id,question_row_id,project_id,raw_answer) "
                    "VALUES (%s,%s,%s,%s,'Validated actual response') "
                    "RETURNING survey_answer_id",
                    (response, assignment, question, ids["project"]),
                ).fetchone()[0]
            evidence, document, document_version, fingerprint = (
                round_fixture.insert_evidence(db, ids)
            )
            db.execute(
                "INSERT INTO plm.srv_answer_evidence_refs(survey_answer_id,"
                "survey_response_id,survey_assignment_id,question_row_id,project_id,"
                "evidence_id,document_id,document_version_id,"
                "observed_evidence_lock_version,content_fingerprint,recorded_by,"
                "recorded_at,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,"
                "statement_timestamp(),0)",
                (answer, response, assignment, question, ids["project"], evidence,
                 document, document_version, fingerprint, pm),
            )
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.srv_assignments SET submission_state='VALIDATED',"
                    "validated_by=%s,validated_at=statement_timestamp(),updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=1 "
                    "WHERE survey_assignment_id=%s", (pm, pm, assignment),
                )
                db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                    "WHERE survey_round_id=%s",
                    (pm, b"c" * 32, pm, round_id),
                )

            action = uuid.uuid4()
            with db.transaction():
                created = db.execute("SELECT statement_timestamp()").fetchone()[0]
                db.execute(
                    "INSERT INTO plm.hnd_action_items(action_item_id,project_id,"
                    "source_kind,source_analysis_version_ref,source_item_id,action_type,"
                    "title,requested_input_spec,owner_ref,due_at,priority,created_by,"
                    "created_reason,created_at,updated_at) VALUES (%s,%s,"
                    "'ANALYSIS_ITEM',%s,%s,'PROVIDE_INFO','Validation blocker',"
                    "'{}'::jsonb,%s,%s+interval '1 day','HIGH',%s,'A05 fixture',%s,%s)",
                    (action, ids["project"], ids["analysis_version"],
                     ids["handover_item"], pm, created, pm, created, created),
                )
                db.execute(
                    "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,"
                    "sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                    "VALUES (%s,%s,0,NULL,'OPEN',%s,'A05 fixture',%s,%s)",
                    (action, ids["project"], pm, created, uuid.uuid4()),
                )

            ai_task, invocation, suggestion = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,"
                    "requested_by,input_fingerprint,prompt_policy_ref,output_schema_ref,"
                    "context_policy_ref,task_state,suggestion_state,current_invocation_ref,"
                    "trace_id,started_at,completed_at) VALUES (%s,'PROJECT',%s,"
                    "'SURVEY_ANALYZE',%s,%s,'survey-analyze.v1','survey-conclusion.v1',"
                    "'project.v1','SUCCEEDED','AVAILABLE',%s,%s,statement_timestamp(),"
                    "statement_timestamp())",
                    (ai_task, ids["project"], pm, b"i" * 32,
                     invocation, uuid.uuid4()),
                )
                db.execute(
                    "INSERT INTO plm.ai_suggestion_payloads(suggestion_payload_id,"
                    "ai_invocation_id,ai_task_id,scope,project_id,output_schema_ref,"
                    "schema_version,canonical_payload,payload_fingerprint,quality_flags) "
                    "VALUES (%s,%s,%s,'PROJECT',%s,'survey-conclusion.v1',1,%s,%s,%s)",
                    (suggestion, invocation, ai_task, ids["project"],
                     Jsonb({"summary": "non-formal draft suggestion"}),
                     b"a" * 32, Jsonb(["REVIEW_REQUIRED"])),
                )

        runtime = create_database_runtime(url)
        guard = Guard()
        guard.enabled = True
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex(),
        )
        evidence_owner = SurveyConclusionProjectRecordProofService(
            evidence=EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=SqlAlchemyProjectAuthorizationRepository(),
                evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                documents=a04.a03.FixedDocument(facts),
                allowed_project_roles=frozenset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                }),
                required_document_category="PROJECT_RECORD",
            ),
        )
        owners = dict(
            response_owner=SqlAlchemyConclusionResponseProof(),
            evidence_owner=evidence_owner,
            issue_owner=SqlAlchemySurveyConclusionIssueProof(),
            ai_owner=SqlAlchemySurveyConclusionAITaskProof(),
        )
        create_service = SurveyConclusionCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization,
            repository=SqlAlchemySurveyConclusionRepository(), **owners,
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            clock=lambda: datetime.now(timezone.utc),
        )
        created = create_service.create(CreateSurveyConclusion(
            pm_token, CSRF, uuid.uuid4(), ids["project"], survey, (round_id,),
            (DepartmentConclusionInput(
                ids["department"], "Department", "Validated conclusion",
                (response,),
            ),),
            (ModuleConclusionInput(
                "PLM.BOM", "Module", "Validated conclusion", (response,),
            ),),
            (ConclusionEvidenceInput(evidence, "SUPPORT"),),
            (ConclusionOpenIssueInput(action, True),), (ai_task,), None,
            str(uuid.uuid4()),
        ))

        def service(audit=None):
            return SurveyConclusionValidationService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization,
                repository=SqlAlchemySurveyConclusionValidationRepository(),
                **owners,
                audit_source=SqlAlchemyConclusionValidationAuditSource(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                audit=audit or AuditService(SqlAlchemyAuditRepository()),
                clock=lambda: datetime.now(timezone.utc),
            )

        def validate(*, token=pm_token, csrf=CSRF, key=None, target=None):
            return (target or service()).validate(ValidateSurveyConclusion(
                token, csrf, uuid.uuid4(), ids["project"],
                created.summary.survey_conclusion_id,
                key or str(uuid.uuid4()),
            ))

        expect("AUTH_ACCESS_DENIED", lambda: validate(csrf=b"x" * 32))
        expect("RESOURCE_NOT_FOUND", lambda: validate(token=customer_token))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", validate)
        guard.enabled = True

        blocked_key = str(uuid.uuid4())
        blocked = validate(key=blocked_key)
        assert not blocked.valid
        assert blocked.issue_codes == ("BLOCKING_OPEN_ISSUE",)
        assert blocked.current_open_blocking_issue_count == 1
        assert validate(key=blocked_key) == blocked

        with schema.connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            changed = db.execute("SELECT statement_timestamp()").fetchone()[0]
            db.execute(
                "UPDATE plm.hnd_action_items SET action_state='CLOSED',lock_version=1,"
                "updated_at=%s WHERE action_item_id=%s", (changed, action),
            )
            db.execute(
                "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,"
                "sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                "VALUES (%s,%s,1,'OPEN','CLOSED',%s,'A05 resolved',%s,%s)",
                (action, ids["project"], pm, changed, uuid.uuid4()),
            )
        passed = validate()
        assert passed.valid and passed.issue_codes == ()
        assert passed.current_open_blocking_issue_count == 0
        assert passed.conclusion_state == "DRAFT"

        rollback_key = str(uuid.uuid4())
        expect("SURVEY_CONCLUSION_UNAVAILABLE", lambda: validate(
            key=rollback_key, target=service(FailedAudit()),
        ))
        assert validate(key=rollback_key).valid

        with schema.connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='A05 drift',lock_version=lock_version+1,"
                "updated_by=%s,updated_at=statement_timestamp() WHERE evidence_id=%s",
                (pm, evidence),
            )
        drift = validate()
        assert not drift.valid
        assert drift.issue_codes == ("EVIDENCE_UNAVAILABLE",)

        with schema.connect(database) as db:
            assert db.execute(
                "SELECT conclusion_state FROM plm.srv_conclusions WHERE "
                "survey_conclusion_id=%s",
                (created.summary.survey_conclusion_id,),
            ).fetchone()[0] == "DRAFT"
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE "
                "action='SURVEY_CONCLUSION_VALIDATED' AND target_version_id=%s",
                (created.summary.survey_conclusion_id,),
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation='V1_SURVEY_CONCLUSION_VALIDATE'",
            ).fetchone()[0] == 4
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with schema.connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database),
            ))
    print(
        "SUR_04_A05_CONCLUSION_VALIDATION_PASS: current CLOSED Round, VALIDATED "
        "chain-tail Response, PROJECT_RECORD, HND-03 and AI provenance reproof; "
        "blocking issue resolution, evidence drift, authorization, License, "
        "idempotent replay, Audit rollback and no state mutation verified on "
        "Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
