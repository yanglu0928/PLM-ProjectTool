"""Windows 11/PostgreSQL 18 proof for Assignment VALIDATE/RETURN matrix."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.survey.application.record_response import RecordSurveyResponse, SurveyResponseRecordService
from plm_assistant.modules.survey.application.review_assignment import ReviewSurveyAssignment, SurveyAssignmentReviewError, SurveyAssignmentReviewService
from plm_assistant.modules.survey.application.submit_assignment import SubmitSurveyAssignment, SurveyAssignmentSubmitService
from plm_assistant.modules.survey.infrastructure.response_repository import SqlAlchemySurveyResponseRepository
from plm_assistant.modules.survey.infrastructure.round_source_repository import SqlAlchemySurveyRoundSourceRepository
from plm_assistant.modules.survey.infrastructure.submission_repository import SqlAlchemySurveyAssignmentSubmissionRepository


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"))
auth = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, definition = schema["connect"], schema["load_definition_fixture"]()
approve_definition, seed_user = schema["approve_definition"], auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


class Unused:
    def prove(self, *args, **kwargs): raise AssertionError("unexpected Evidence proof")
    def append(self, *args, **kwargs): raise AssertionError("unexpected source append")


def expect(code, action):
    try: action()
    except SurveyAssignmentReviewError as error:
        assert error.code == code, (error.code, code); return
    raise AssertionError("expected " + code)


def main() -> None:
    database = "sur03a06_" + uuid.uuid4().hex[:8]
    tokens = {"pm": b"p" * 32, "im": b"i" * 32, "c1": b"1" * 32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            users = {name: seed_user(db, "Review " + name, "NONE", tokens[name])
                     for name in tokens}
            for name, role in (("pm", "PROJECT_MANAGER"),
                               ("im", "IMPLEMENTATION_MEMBER"),
                               ("c1", "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], users[name], ids["department"], role))
            survey, version = definition.insert_valid(db, ids, name="Review state survey")
            question_row, question_id = db.execute(
                "SELECT question_row_id,question_id FROM plm.srv_questions WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,)).fetchone()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.srv_questions SET required=false WHERE survey_version_id=%s AND question_row_id<>%s", (version, question_row))
            approve_definition(db, ids, survey, version)
            round_id = uuid.uuid4()
            assignments = {name: uuid.uuid4() for name in ("c1", "im", "pm")}
            roots = {name: uuid.uuid4() for name in assignments}
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("INSERT INTO plm.srv_rounds(survey_round_id,survey_id,survey_version_id,project_id,round_no,round_state,opened_by,opened_at,created_by,updated_by,lock_version) VALUES (%s,%s,%s,%s,1,'OPEN',%s,statement_timestamp(),%s,%s,1)",
                           (round_id, survey, version, ids["project"], users["pm"], users["pm"], users["pm"]))
                for name, assignment_id in assignments.items():
                    actor = users[name]
                    db.execute("INSERT INTO plm.srv_assignments(survey_assignment_id,survey_round_id,survey_id,survey_version_id,project_id,department_id,assignee_user_id,submission_state,submitted_by,submitted_at,created_by,updated_by,lock_version) VALUES (%s,%s,%s,%s,%s,%s,%s,'SUBMITTED',%s,statement_timestamp(),%s,%s,2)",
                               (assignment_id, round_id, survey, version, ids["project"], ids["department"], actor, actor, users["pm"], actor))
                    db.execute("INSERT INTO plm.srv_responses(survey_response_id,survey_assignment_id,survey_round_id,survey_id,survey_version_id,project_id,question_row_id,response_source,recorded_by,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,statement_timestamp())",
                               (roots[name], assignment_id, round_id, survey, version, ids["project"], question_row, actor))
                    db.execute("INSERT INTO plm.srv_answers(survey_response_id,survey_assignment_id,question_row_id,project_id,answer_value) VALUES (%s,%s,%s,%s,to_jsonb(%s::text))",
                               (roots[name], assignment_id, question_row, ids["project"], "old"))

        runtime = create_database_runtime(url); now = lambda: datetime.now(timezone.utc)
        guard = Guard(); guard.enabled = True
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        receipts = SqlAlchemyIdempotencyReceipts(); audit = AuditService(SqlAlchemyAuditRepository())
        repository = SqlAlchemySurveyAssignmentSubmissionRepository()
        def reviewer(selected_audit=None): return SurveyAssignmentReviewService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization, repository=repository,
            receipts=receipts, audit=selected_audit or audit,
            evidence_owner=Unused(), clock=now)
        def review(actor, target, assignment, expected, key=None, comment=None, owner=None, csrf=CSRF):
            command_value = ReviewSurveyAssignment(
                tokens[actor], csrf, uuid.uuid4(), ids["project"], round_id,
                assignments[assignment], expected, comment, key or str(uuid.uuid4()))
            return ((owner or reviewer()).validate(command_value) if target == "VALIDATED"
                    else (owner or reviewer()).return_assignment(command_value))

        key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            validated = list(pool.map(
                lambda _: review("pm", "VALIDATED", "c1", 2, key), range(2)))
        assert validated[0] == validated[1] and validated[0].etag == '"v3"'
        returned = review("im", "RETURNED", "im", 2, comment="  请补充实际记录  ")
        assert returned.return_comment == "请补充实际记录"
        expect("RESOURCE_NOT_FOUND", lambda: review("c1", "RETURNED", "pm", 2, comment="x"))
        expect("AUTH_ACCESS_DENIED", lambda: review("pm", "RETURNED", "pm", 2, comment="x", csrf=b"x" * 32))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: review("pm", "RETURNED", "pm", 2, comment="x"))
        guard.enabled = True

        response_owner = SurveyResponseRecordService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyResponseRepository(), receipts=receipts,
            audit=audit, evidence_owner=Unused(), round_record_proof=Unused(),
            round_source_repository=SqlAlchemySurveyRoundSourceRepository(), clock=now)
        corrected = response_owner.record(RecordSurveyResponse(
            tokens["im"], CSRF, uuid.uuid4(), ids["project"], round_id,
            assignments["im"], question_id, 3, "SELF_SERVICE", None,
            "corrected", (), None, roots["im"], str(uuid.uuid4())))
        assert corrected.assignment_etag == '"v4"'
        submit_owner = SurveyAssignmentSubmitService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization, repository=repository,
            receipts=receipts, audit=audit, evidence_owner=Unused(), clock=now)
        submitted = submit_owner.submit(SubmitSurveyAssignment(
            tokens["im"], CSRF, uuid.uuid4(), ids["project"], round_id,
            assignments["im"], 4, str(uuid.uuid4())))
        assert submitted.etag == '"v5"'
        final = review("pm", "VALIDATED", "im", 5)
        assert final.etag == '"v6"'

        rollback_key = str(uuid.uuid4())
        expect("SURVEY_ASSIGNMENT_UNAVAILABLE", lambda: review(
            "pm", "RETURNED", "pm", 2, rollback_key, "需补充", reviewer(FailedAudit())))
        recovered = review("pm", "RETURNED", "pm", 2, rollback_key, "需补充")
        assert recovered.submission_state == "RETURNED"
        expect("SURVEY_ASSIGNMENT_STATE_INVALID", lambda: review(
            "pm", "VALIDATED", "c1", 3))

        with connect(database) as db:
            states = db.execute("SELECT submission_state,count(*) FROM plm.srv_assignments GROUP BY submission_state ORDER BY submission_state").fetchall()
            actions = db.execute("SELECT action,count(*) FROM plm.aud_events WHERE action IN ('SURVEY_ASSIGNMENT_VALIDATED','SURVEY_ASSIGNMENT_RETURNED') GROUP BY action ORDER BY action").fetchall()
            assert states == [("RETURNED", 1), ("VALIDATED", 2)], states
            assert actions == [("SURVEY_ASSIGNMENT_RETURNED", 2), ("SURVEY_ASSIGNMENT_VALIDATED", 2)], actions
            assert db.execute("SELECT count(*) FROM plm.srv_responses WHERE survey_assignment_id=%s", (assignments["im"],)).fetchone()[0] == 2
        command.check(create_migration_config(url))
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
    print("SUR_03_A06_ASSIGNMENT_REVIEW_PASS: concurrent VALIDATE, RETURN, rollback, RETURNED correction/resubmit/validate matrix, role/CSRF/License/terminal refusal verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
