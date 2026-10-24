"""Windows 11/PostgreSQL 18 proof for Survey Assignment SUBMIT."""

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
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.prove_fixed_source import VerifiedFixedSource
from plm_assistant.modules.document.application.read_documents import DocumentEvidenceSourceFacts
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.survey.application.change_round import OpenSurveyRound, SurveyRoundStateService
from plm_assistant.modules.survey.application.create_assignment import CreateSurveyAssignment, SurveyAssignmentCreateService
from plm_assistant.modules.survey.application.create_round import CreateSurveyRound, SurveyRoundCreateService
from plm_assistant.modules.survey.application.record_response import RecordSurveyResponse, SurveyResponseRecordService
from plm_assistant.modules.survey.application.submit_assignment import SubmitSurveyAssignment, SurveyAssignmentSubmitError, SurveyAssignmentSubmitService
from plm_assistant.modules.survey.infrastructure.assignment_repository import SqlAlchemySurveyAssignmentRepository
from plm_assistant.modules.survey.infrastructure.response_repository import SqlAlchemySurveyResponseRepository
from plm_assistant.modules.survey.infrastructure.round_repository import SqlAlchemySurveyRoundRepository
from plm_assistant.modules.survey.infrastructure.round_source_repository import SqlAlchemySurveyRoundSourceRepository
from plm_assistant.modules.survey.infrastructure.round_state_repository import SqlAlchemySurveyRoundStateRepository
from plm_assistant.modules.survey.infrastructure.submission_repository import SqlAlchemySurveyAssignmentSubmissionRepository


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"))
auth = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, definition = schema["connect"], schema["load_definition_fixture"]()
approve_definition, insert_evidence = schema["approve_definition"], schema["insert_evidence"]
seed_user = auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


class FixedDocument:
    def __init__(self, facts): self.facts = facts
    def prove(self, transaction, query, **kwargs): return VerifiedFixedSource(self.facts)


def expect(code, action):
    try: action()
    except SurveyAssignmentSubmitError as error:
        assert error.code == code, (error.code, code); return
    raise AssertionError("expected " + code)


def main() -> None:
    database = "sur03a05_" + uuid.uuid4().hex[:8]
    tokens = {"pm": b"p" * 32, "im": b"i" * 32,
              "c1": b"1" * 32, "c2": b"2" * 32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            users = {name: seed_user(db, "Submit " + name, "NONE", tokens[name])
                     for name in tokens}
            for name, role in (("pm", "PROJECT_MANAGER"), ("im", "IMPLEMENTATION_MEMBER"),
                               ("c1", "CUSTOMER_MANAGER"), ("c2", "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], users[name], ids["department"], role))
            survey, version = definition.insert_valid(db, ids, name="Submit survey")
            questions = db.execute("SELECT question_row_id,question_id,answer_type FROM plm.srv_questions WHERE survey_version_id=%s ORDER BY sequence_no", (version,)).fetchall()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.srv_questions SET validation_rule=%s::jsonb WHERE question_row_id=%s",
                           ('{"min_length":2,"max_length":3}', questions[0][0]))
                db.execute("UPDATE plm.srv_questions SET condition_rule=%s::jsonb WHERE question_row_id=%s",
                           ('{"question_ref":"' + str(questions[0][1]) + '","operator":"EQUALS","value":"YES"}', questions[1][0]))
                db.execute("UPDATE plm.srv_questions SET evidence_required=true WHERE question_row_id=%s", (questions[3][0],))
            approve_definition(db, ids, survey, version)
            evidences = [insert_evidence(db, ids) for _ in range(3)]

        runtime = create_database_runtime(url); now = lambda: datetime.now(timezone.utc)
        guard = Guard(); guard.enabled = True
        project_repo = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=project_repo)
        receipts = SqlAlchemyIdempotencyReceipts(); audit = AuditService(SqlAlchemyAuditRepository())
        round_view = SurveyRoundCreateService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyRoundRepository(), receipts=receipts,
            audit=audit, clock=now).create(CreateSurveyRound(
                tokens["pm"], CSRF, uuid.uuid4(), ids["project"], survey, version,
                None, None, None, str(uuid.uuid4())))
        SurveyRoundStateService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyRoundStateRepository(), receipts=receipts,
            audit=audit, clock=now).open(OpenSurveyRound(
                tokens["pm"], CSRF, uuid.uuid4(), ids["project"],
                round_view.survey_round_id, 0, str(uuid.uuid4())))
        assignment_owner = SurveyAssignmentCreateService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyAssignmentRepository(), receipts=receipts,
            audit=audit, clock=now)
        def assign(user): return assignment_owner.create(CreateSurveyAssignment(
            tokens["pm"], CSRF, uuid.uuid4(), ids["project"], round_view.survey_round_id,
            ids["department"], users[user], str(uuid.uuid4())))
        assignments = {name: assign(name) for name in ("c1", "c2", "im")}

        document, document_version, fingerprint = evidences[0][1:]
        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex(), "record.pdf")
        evidence_owner = EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(), projects=project_repo,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(), documents=FixedDocument(facts),
            allowed_project_roles=frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"}))
        response_owner = SurveyResponseRecordService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyResponseRepository(), receipts=receipts,
            audit=audit, evidence_owner=evidence_owner, round_record_proof=object(),
            round_source_repository=SqlAlchemySurveyRoundSourceRepository(), clock=now)
        def answers(name, evidence_id):
            assignment = assignments[name]; version_no = 0
            for index, value in ((0, "NO"), (2, "YES"), (3, "note")):
                result = response_owner.record(RecordSurveyResponse(
                    tokens[name], CSRF, uuid.uuid4(), ids["project"], round_view.survey_round_id,
                    assignment.survey_assignment_id, questions[index][1], version_no,
                    "SELF_SERVICE", None, value,
                    (evidence_id,) if index == 3 else (), None, None, str(uuid.uuid4())))
                version_no += 1
            return version_no
        versions = {name: answers(name, evidences[index][0])
                    for index, name in enumerate(("c1", "c2", "im"))}

        def submit_owner(selected_audit=None): return SurveyAssignmentSubmitService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyAssignmentSubmissionRepository(), receipts=receipts,
            audit=selected_audit or audit, evidence_owner=evidence_owner, clock=now)
        def submit(name, key=None, owner=None, csrf=CSRF):
            return (owner or submit_owner()).submit(SubmitSurveyAssignment(
                tokens[name], csrf, uuid.uuid4(), ids["project"], round_view.survey_round_id,
                assignments[name].survey_assignment_id, versions[name],
                key or str(uuid.uuid4())))

        with connect(database) as db:
            db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',eligibility_reason='drift',updated_by=%s,updated_at=statement_timestamp(),lock_version=lock_version+1 WHERE evidence_id=%s", (ids["actor"], evidences[0][0]))
        expect("SURVEY_ASSIGNMENT_INCOMPLETE", lambda: submit("c1"))
        expect("RESOURCE_NOT_FOUND", lambda: submit_owner().submit(SubmitSurveyAssignment(
            tokens["pm"], CSRF, uuid.uuid4(), ids["project"], round_view.survey_round_id,
            assignments["c1"].survey_assignment_id, versions["c1"], str(uuid.uuid4()))))
        expect("AUTH_ACCESS_DENIED", lambda: submit("c1", csrf=b"x" * 32))

        key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            raced = list(pool.map(lambda _: submit("c2", key), range(2)))
        assert raced[0] == raced[1] and raced[0].submission_state == "SUBMITTED"
        rollback_key = str(uuid.uuid4())
        expect("SURVEY_ASSIGNMENT_UNAVAILABLE", lambda: submit(
            "im", rollback_key, submit_owner(FailedAudit())))
        recovered = submit("im", rollback_key)
        assert recovered.submission_state == "SUBMITTED"
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: submit("c1"))
        guard.enabled = True

        with connect(database) as db:
            states = db.execute("SELECT submission_state,count(*) FROM plm.srv_assignments GROUP BY submission_state ORDER BY submission_state").fetchall()
            actions = db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SURVEY_ASSIGNMENT_SUBMITTED'").fetchone()[0]
            idem = db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_SURVEY_ASSIGNMENT_SUBMIT'").fetchone()[0]
            assert states == [("IN_PROGRESS", 1), ("SUBMITTED", 2)], states
            assert (actions, idem) == (2, 2)
        command.check(create_migration_config(url))
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
    print("SUR_03_A05_ASSIGNMENT_SUBMIT_PASS: condition/required/validation/Evidence completeness, drift refusal, concurrent replay, Audit rollback, role/CSRF/License verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
