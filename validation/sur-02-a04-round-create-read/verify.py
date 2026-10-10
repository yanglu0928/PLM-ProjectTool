"""Windows 11/PostgreSQL 18 proof for Survey Round create/list/get."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.survey.application.create_round import (
    CreateSurveyRound,
    SurveyRoundCreateError,
    SurveyRoundCreateService,
)
from plm_assistant.modules.survey.application.read_rounds import (
    SurveyRoundReadError,
    SurveyRoundReadQuery,
    SurveyRoundReadService,
)
from plm_assistant.modules.survey.infrastructure.round_repository import (
    SqlAlchemySurveyRoundRepository,
)


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"
))
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect = schema["connect"]
definition = schema["load_definition_fixture"]()
approve_definition = schema["approve_definition"]
insert_evidence = schema["insert_evidence"]
seed_user = auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


def expect_create(code: str, action) -> None:
    try:
        action()
    except SurveyRoundCreateError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected create failure: " + code)


def expect_read(code: str, action) -> None:
    try:
        action()
    except SurveyRoundReadError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected read failure: " + code)


def main() -> None:
    database = "sur02a04_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            pm = seed_user(db, "Round PM", "NONE", pm_token)
            implementation = seed_user(db, "Round Implementer", "NONE", impl_token)
            customer = seed_user(db, "Round Customer", "NONE", customer_token)
            for actor, role in (
                (pm, "PROJECT_MANAGER"),
                (implementation, "IMPLEMENTATION_MEMBER"),
                (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,"
                    "department_id,project_role) VALUES (%s,%s,%s,%s)",
                    (ids["project"], actor, ids["department"], role),
                )
            survey, version = definition.insert_valid(
                db, ids, name="Approved Round runtime survey",
            )
            approve_definition(db, ids, survey, version)
            draft_survey, draft_version = definition.insert_valid(
                db, ids, name="Draft Round runtime survey",
            )
            question_id = db.execute(
                "SELECT question_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,),
            ).fetchone()[0]

        runtime = create_database_runtime(url)
        guard = Guard()
        guard.enabled = True
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        repository = SqlAlchemySurveyRoundRepository()
        common = dict(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=guard,
            authorization=authorization,
            repository=repository,
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )

        def create_service(audit=None):
            return SurveyRoundCreateService(
                **common,
                audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        def create(
            *, token=pm_token, csrf=CSRF, selected_survey=survey,
            selected_version=version, key=None, location="Customer site",
            target=None,
        ):
            now = datetime(2026, 10, 7, tzinfo=timezone.utc)
            return (target or create_service()).create(CreateSurveyRound(
                token, csrf, uuid.uuid4(), ids["project"], selected_survey,
                selected_version, now + timedelta(hours=1),
                now + timedelta(hours=2), location, key or str(uuid.uuid4()),
            ))

        expect_create("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
        expect_create("RESOURCE_NOT_FOUND", lambda: create(token=customer_token))
        expect_create("SURVEY_VERSION_NOT_APPROVED", lambda: create(
            selected_survey=draft_survey, selected_version=draft_version,
        ))
        guard.enabled = False
        expect_create("LICENSE_OPERATION_DENIED", create)
        guard.enabled = True

        first_key = str(uuid.uuid4())
        first = create(key=first_key)
        replay = create(key=first_key)
        assert first == replay and first.round_no == 1 and first.etag == '"v0"'
        expect_create("CONFLICT_IDEMPOTENCY", lambda: create(
            key=first_key, location="Changed site",
        ))
        second = create(token=impl_token, location=None)
        assert second.round_no == 2 and second.created_by == implementation

        concurrent_key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(
                lambda _: create(key=concurrent_key, location="Concurrent site"),
                range(2),
            ))
        assert concurrent[0] == concurrent[1] and concurrent[0].round_no == 3

        rollback_key = str(uuid.uuid4())
        expect_create("SURVEY_ROUND_UNAVAILABLE", lambda: create(
            key=rollback_key, location="Rollback site",
            target=create_service(FailedAudit()),
        ))
        recovered = create(key=rollback_key, location="Rollback site")
        assert recovered.round_no == 4

        reads = SurveyRoundReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=guard,
            authorization=authorization, repository=repository,
            clock=lambda: datetime.now(timezone.utc),
        )
        customer_query = SurveyRoundReadQuery(
            customer_token, uuid.uuid4(), ids["project"],
        )
        page1 = reads.list_rounds(customer_query, page_size=2)
        assert page1.has_more and len(page1.items) == 2
        page2 = reads.list_rounds(
            customer_query, page_size=2,
            after_created_at=page1.next_created_at,
            after_round_id=page1.next_round_id,
        )
        assert len(page2.items) == 2 and not page2.has_more
        assert not set(item.survey_round_id for item in page1.items) & set(
            item.survey_round_id for item in page2.items
        )
        detail = reads.get_round(customer_query, first.survey_round_id)
        assert detail.source_record_count == 0 and detail.source_records == ()
        expect_read("RESOURCE_NOT_FOUND", lambda: reads.get_round(
            SurveyRoundReadQuery(customer_token, uuid.uuid4(), uuid.uuid4()),
            first.survey_round_id,
        ))

        with connect(database) as db:
            evidence, document, document_version, fingerprint = insert_evidence(db, ids)
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s",
                (pm, pm, first.survey_round_id),
            )
            db.execute(
                """
                INSERT INTO plm.srv_round_source_records(
                  survey_round_id,survey_id,survey_version_id,project_id,
                  question_row_id,document_id,document_version_id,evidence_id,
                  observed_evidence_lock_version,content_fingerprint,
                  recorded_by,recorded_at,ordinal)
                SELECT %s,%s,%s,%s,q.question_row_id,%s,%s,%s,0,%s,%s,
                  statement_timestamp(),0
                FROM plm.srv_questions q
                WHERE q.survey_version_id=%s AND q.question_id=%s
                """,
                (
                    first.survey_round_id, survey, version, ids["project"],
                    document, document_version, evidence, fingerprint, pm,
                    version, question_id,
                ),
            )
        detail = reads.get_round(customer_query, first.survey_round_id)
        assert detail.round_state == "OPEN" and detail.etag == '"v1"'
        assert detail.source_record_count == 1
        assert detail.source_records[0].question_id == question_id
        assert detail.source_records[0].content_fingerprint == fingerprint

        with connect(database) as db:
            assert db.execute(
                "SELECT array_agg(round_no ORDER BY round_no) FROM plm.srv_rounds "
                "WHERE survey_id=%s", (survey,),
            ).fetchone()[0] == [1, 2, 3, 4]
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE "
                "action='SURVEY_ROUND_CREATED' AND target_project_id=%s",
                (ids["project"],),
            ).fetchone()[0] == 4
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation='V1_SURVEY_ROUND_CREATE'",
            ).fetchone()[0] == 4
            db.execute(
                "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                "WHERE project_id=%s AND user_id=%s",
                (ids["project"], customer),
            )
        expect_read("RESOURCE_NOT_FOUND", lambda: reads.get_round(
            customer_query, first.survey_round_id,
        ))
        command.check(create_migration_config(url))
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
            )
    print(
        "SUR_02_A04_ROUND_CREATE_READ_PASS: current APPROVED definition, PM/"
        "Implementation create, Session/CSRF/License, idempotency concurrency, "
        "Audit rollback, continuous round numbers, member pagination/detail, fixed "
        "source projection, isolation and revocation verified on Windows 11/PG18"
    )


if __name__ == "__main__":
    main()
