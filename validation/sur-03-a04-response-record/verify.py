"""Windows 11/PostgreSQL 18 proof for atomic Survey response recording."""

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
from plm_assistant.modules.survey.application.record_response import RecordSurveyResponse, SurveyResponseRecordError, SurveyResponseRecordService
from plm_assistant.modules.survey.application.round_source import SurveyRoundProjectRecordProofService
from plm_assistant.modules.survey.infrastructure.assignment_repository import SqlAlchemySurveyAssignmentRepository
from plm_assistant.modules.survey.infrastructure.response_repository import SqlAlchemySurveyResponseRepository
from plm_assistant.modules.survey.infrastructure.round_repository import SqlAlchemySurveyRoundRepository
from plm_assistant.modules.survey.infrastructure.round_source_repository import SqlAlchemySurveyRoundSourceRepository
from plm_assistant.modules.survey.infrastructure.round_state_repository import SqlAlchemySurveyRoundStateRepository


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
    except SurveyResponseRecordError as error:
        assert error.code == code, (error.code, code); return
    raise AssertionError("expected " + code)


def main() -> None:
    database = "sur03a04_" + uuid.uuid4().hex[:8]
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
            users = {name: seed_user(db, "Response " + name, "NONE", tokens[name])
                     for name in tokens}
            for name, role in (("pm", "PROJECT_MANAGER"),
                               ("im", "IMPLEMENTATION_MEMBER"),
                               ("c1", "CUSTOMER_MANAGER"),
                               ("c2", "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,"
                           "department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], users[name], ids["department"], role))
            survey, version = definition.insert_valid(db, ids, name="Response owner survey")
            approve_definition(db, ids, survey, version)
            questions = db.execute(
                "SELECT question_id,answer_type FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no", (version,)).fetchall()
            evidence, document, document_version, fingerprint = insert_evidence(db, ids)
            facilitated_evidence, _, _, _ = insert_evidence(db, ids)
            rollback_evidence, _, _, _ = insert_evidence(db, ids)

        runtime = create_database_runtime(url)
        guard = Guard(); guard.enabled = True
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository)
        receipts = SqlAlchemyIdempotencyReceipts()
        audit = AuditService(SqlAlchemyAuditRepository())
        now = lambda: datetime.now(timezone.utc)
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

        assignment_service = SurveyAssignmentCreateService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyAssignmentRepository(), receipts=receipts,
            audit=audit, clock=now)
        def assignment(assignee):
            return assignment_service.create(CreateSurveyAssignment(
                tokens["pm"], CSRF, uuid.uuid4(), ids["project"],
                round_view.survey_round_id, ids["department"], assignee,
                str(uuid.uuid4())))
        a_self, a_facilitated, a_denied, a_rollback, a_race = (
            assignment(users["c1"]), assignment(users["c2"]),
            assignment(users["pm"]), assignment(users["im"]),
            assignment(None),
        )

        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex())
        common = dict(
            sessions=SqlAlchemyProjectReadAccess(), projects=project_repository,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=FixedDocument(facts))
        general_evidence = EvidenceFixedProjectSourceService(
            **common, allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"}))
        round_evidence = EvidenceFixedProjectSourceService(
            **common, allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
            required_document_category="PROJECT_RECORD")
        repository = SqlAlchemySurveyResponseRepository()
        def response_service(selected_audit=None):
            return SurveyResponseRecordService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization, repository=repository,
                receipts=receipts, audit=selected_audit or audit,
                evidence_owner=general_evidence,
                round_record_proof=SurveyRoundProjectRecordProofService(
                    evidence=round_evidence),
                round_source_repository=SqlAlchemySurveyRoundSourceRepository(),
                clock=now)
        def record(name, assigned, *, expected=0, source="SELF_SERVICE",
                   answer="answer", evidence_ids=(), source_evidence=None,
                   correction=None, key=None, service=None, csrf=CSRF):
            return (service or response_service()).record(RecordSurveyResponse(
                tokens[name], csrf, uuid.uuid4(), ids["project"],
                round_view.survey_round_id, assigned.survey_assignment_id,
                questions[0][0], expected, source, None, answer,
                evidence_ids, source_evidence, correction,
                key or str(uuid.uuid4())))

        first = record("c1", a_self, evidence_ids=(evidence,))
        assert first.assignment_etag == '"v1"' and first.evidence_count == 1
        corrected = record(
            "c1", a_self, expected=1, answer="corrected",
            correction=first.survey_response_id)
        assert corrected.assignment_etag == '"v2"'
        facilitated = record(
            "im", a_facilitated, source="FACILITATED_RECORD",
            source_evidence=facilitated_evidence)
        assert facilitated.round_source_record_ref_id is not None
        assert facilitated.evidence_count == 1
        expect("RESOURCE_NOT_FOUND", lambda: record(
            "pm", a_denied, source="FACILITATED_RECORD",
            source_evidence=rollback_evidence))
        expect("RESOURCE_NOT_FOUND", lambda: record("im", a_denied))
        expect("AUTH_ACCESS_DENIED", lambda: record(
            "c2", a_denied, csrf=b"x" * 32))

        rollback_key = str(uuid.uuid4())
        expect("SURVEY_RESPONSE_UNAVAILABLE", lambda: record(
            "im", a_rollback, source="FACILITATED_RECORD",
            source_evidence=rollback_evidence, key=rollback_key,
            service=response_service(FailedAudit())))
        recovered = record(
            "im", a_rollback, source="FACILITATED_RECORD",
            source_evidence=rollback_evidence, key=rollback_key)
        assert recovered.evidence_count == 1

        race_key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            raced = list(pool.map(
                lambda _: record("c2", a_race, key=race_key), range(2)))
        assert raced[0] == raced[1]

        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: record("c2", a_denied))
        guard.enabled = True
        with connect(database) as db:
            response_count = db.execute(
                "SELECT count(*) FROM plm.srv_responses").fetchone()[0]
            answer_count = db.execute(
                "SELECT count(*) FROM plm.srv_answers").fetchone()[0]
            source_count = db.execute(
                "SELECT count(*) FROM plm.srv_round_source_records").fetchone()[0]
            audit_count = db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE "
                "action='SURVEY_RESPONSE_RECORDED'").fetchone()[0]
            receipt_count = db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation='V1_SURVEY_RESPONSE_RECORD'").fetchone()[0]
            assert (response_count, answer_count, source_count,
                    audit_count, receipt_count) == (5, 5, 2, 5, 5)
            chain = db.execute(
                "SELECT correction_of_response_id FROM plm.srv_responses "
                "WHERE survey_response_id=%s", (corrected.survey_response_id,)
            ).fetchone()[0]
            assert chain == first.survey_response_id
        command.check(create_migration_config(url))
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print("SUR_03_A04_RESPONSE_RECORD_PASS: self-service/facilitated append, fixed "
          "Evidence, correction chain, concurrent idempotency, Audit rollback, "
          "role/CSRF/License boundaries verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
