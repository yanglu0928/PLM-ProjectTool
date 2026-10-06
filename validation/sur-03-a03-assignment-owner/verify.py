"""Windows 11/PostgreSQL 18 proof for Survey Assignment create/read ownership."""

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
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.survey.application.create_assignment import (
    CreateSurveyAssignment, SurveyAssignmentCreateError, SurveyAssignmentCreateService,
)
from plm_assistant.modules.survey.application.read_assignments import (
    SurveyAssignmentReadError, SurveyAssignmentReadQuery, SurveyAssignmentReadService,
)
from plm_assistant.modules.survey.application.create_round import CreateSurveyRound, SurveyRoundCreateService
from plm_assistant.modules.survey.application.change_round import OpenSurveyRound, SurveyRoundStateService
from plm_assistant.modules.survey.infrastructure.assignment_repository import SqlAlchemySurveyAssignmentRepository
from plm_assistant.modules.survey.infrastructure.round_repository import SqlAlchemySurveyRoundRepository
from plm_assistant.modules.survey.infrastructure.round_state_repository import SqlAlchemySurveyRoundStateRepository


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"))
auth = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, definition = schema["connect"], schema["load_definition_fixture"]()
approve_definition, seed_user = schema["approve_definition"], auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


def expect(error_type, code, action):
    try: action()
    except error_type as error:
        assert error.code == code, (error.code, code); return
    raise AssertionError("expected " + code)


def main() -> None:
    database = "sur03a03_" + uuid.uuid4().hex[:8]
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
            users = {name: seed_user(db, "Assignment " + name, "NONE", tokens[name])
                     for name in tokens}
            for name, role in (("pm", "PROJECT_MANAGER"),
                               ("im", "IMPLEMENTATION_MEMBER"),
                               ("c1", "CUSTOMER_MANAGER"),
                               ("c2", "CUSTOMER_MEMBER")):
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,"
                           "department_id,project_role) VALUES (%s,%s,%s,%s)",
                           (ids["project"], users[name], ids["department"], role))
            survey, version = definition.insert_valid(db, ids, name="Assignment owner survey")
            approve_definition(db, ids, survey, version)

        runtime = create_database_runtime(url)
        guard = Guard(); guard.enabled = True
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        receipts = SqlAlchemyIdempotencyReceipts()
        audit = AuditService(SqlAlchemyAuditRepository())
        round_repo = SqlAlchemySurveyRoundRepository()
        round_create = SurveyRoundCreateService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization, repository=round_repo,
            receipts=receipts, audit=audit, clock=lambda: datetime.now(timezone.utc))
        round_view = round_create.create(CreateSurveyRound(
            tokens["pm"], CSRF, uuid.uuid4(), ids["project"], survey, version,
            None, None, None, str(uuid.uuid4())))
        round_state = SurveyRoundStateService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemySurveyRoundStateRepository(), receipts=receipts,
            audit=audit, clock=lambda: datetime.now(timezone.utc))
        round_state.open(OpenSurveyRound(
            tokens["pm"], CSRF, uuid.uuid4(), ids["project"],
            round_view.survey_round_id, 0, str(uuid.uuid4())))

        repo = SqlAlchemySurveyAssignmentRepository()
        def service(selected_audit=None):
            return SurveyAssignmentCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization, repository=repo, receipts=receipts,
                audit=selected_audit or audit, clock=lambda: datetime.now(timezone.utc))
        def create(name="pm", assignee=None, key=None, target=None, department=None):
            return (target or service()).create(CreateSurveyAssignment(
                tokens[name], CSRF, uuid.uuid4(), ids["project"],
                round_view.survey_round_id, department or ids["department"],
                assignee, key or str(uuid.uuid4())))

        expect(SurveyAssignmentCreateError, "RESOURCE_NOT_FOUND", lambda: create("c1"))
        expect(SurveyAssignmentCreateError, "RESOURCE_NOT_FOUND",
               lambda: create(department=uuid.uuid4()))
        key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            raced = list(pool.map(lambda _: create(key=key), range(2)))
        assert raced[0] == raced[1] and raced[0].assignee_user_id is None
        one = create("im", users["c1"])
        two = create("pm", users["c2"])

        rollback_key = str(uuid.uuid4())
        expect(SurveyAssignmentCreateError, "SURVEY_ASSIGNMENT_UNAVAILABLE",
               lambda: create("im", users["im"], rollback_key,
                              service(FailedAudit())))
        recovered = create("im", users["im"], rollback_key)
        assert recovered.submission_state == "ASSIGNED"

        reads = SurveyAssignmentReadService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
            license_guard=guard, authorization=authorization, repository=repo,
            clock=lambda: datetime.now(timezone.utc))
        def query(name): return SurveyAssignmentReadQuery(
            tokens[name], uuid.uuid4(), ids["project"], round_view.survey_round_id)
        page1 = reads.list_assignments(query("pm"), page_size=2)
        page2 = reads.list_assignments(
            query("pm"), page_size=2, after_created_at=page1.next_created_at,
            after_assignment_id=page1.next_assignment_id)
        assert page1.has_more and not page2.has_more
        assert len(page1.items) + len(page2.items) == 4
        c1_items = reads.list_assignments(query("c1"), page_size=10).items
        assert {item.survey_assignment_id for item in c1_items} == {
            raced[0].survey_assignment_id, one.survey_assignment_id}
        expect(SurveyAssignmentReadError, "RESOURCE_NOT_FOUND",
               lambda: reads.get_assignment(query("c1"), two.survey_assignment_id))
        assert reads.get_assignment(query("c1"), one.survey_assignment_id) == one

        guard.enabled = False
        expect(SurveyAssignmentReadError, "LICENSE_OPERATION_DENIED",
               lambda: reads.list_assignments(query("pm"), page_size=10))
        guard.enabled = True
        with connect(database) as db:
            actions = db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                                 "action='SURVEY_ASSIGNMENT_CREATED'").fetchone()[0]
            idem = db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                              "operation='V1_SURVEY_ASSIGNMENT_CREATE'").fetchone()[0]
            assert actions == 4 and idem == 4
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE "
                       "project_id=%s AND user_id=%s", (ids["project"], users["c1"]))
        expect(SurveyAssignmentReadError, "RESOURCE_NOT_FOUND",
               lambda: reads.list_assignments(query("c1"), page_size=10))
        command.check(create_migration_config(url))
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
    print("SUR_03_A03_ASSIGNMENT_OWNER_PASS: PM/Implementation create, target/assignee, "
          "concurrent idempotency, Audit rollback, stable paging, manager/assignee/"
          "department visibility, revocation and License verified on Windows 11/PG18")


if __name__ == "__main__": main()
