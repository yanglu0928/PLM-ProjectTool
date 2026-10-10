"""Windows 11/PostgreSQL 18 proof for Survey Round state ownership."""

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
from plm_assistant.modules.survey.application.change_round import (
    CancelSurveyRound,
    CloseSurveyRound,
    OpenSurveyRound,
    PatchSurveyRound,
    SurveyRoundStateError,
    SurveyRoundStateService,
)
from plm_assistant.modules.survey.application.create_round import (
    CreateSurveyRound,
    SurveyRoundCreateService,
)
from plm_assistant.modules.survey.infrastructure.round_repository import (
    SqlAlchemySurveyRoundRepository,
)
from plm_assistant.modules.survey.infrastructure.round_state_repository import (
    SqlAlchemySurveyRoundStateRepository,
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
seed_user = auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


def expect(code: str, action) -> None:
    try:
        action()
    except SurveyRoundStateError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected Survey Round state failure: " + code)


def main() -> None:
    database = "sur02a05_" + uuid.uuid4().hex[:8]
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
            pm = seed_user(db, "Round State PM", "NONE", pm_token)
            implementation = seed_user(
                db, "Round State Implementer", "NONE", impl_token,
            )
            customer = seed_user(db, "Round State Customer", "NONE", customer_token)
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
                db, ids, name="Approved Round state survey",
            )
            approve_definition(db, ids, survey, version)

        runtime = create_database_runtime(url)
        guard = Guard()
        guard.enabled = True
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        receipts = SqlAlchemyIdempotencyReceipts()
        audit = AuditService(SqlAlchemyAuditRepository())
        creator = SurveyRoundCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, repository=SqlAlchemySurveyRoundRepository(),
            receipts=receipts, audit=audit,
            clock=lambda: datetime.now(timezone.utc),
        )

        def state_service(selected_audit=None):
            return SurveyRoundStateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                authorization=authorization,
                repository=SqlAlchemySurveyRoundStateRepository(),
                receipts=receipts, audit=selected_audit or audit,
                clock=lambda: datetime.now(timezone.utc),
            )

        scheduled = datetime(2026, 10, 8, tzinfo=timezone.utc)

        def create(token=pm_token, label="Original site"):
            return creator.create(CreateSurveyRound(
                token, CSRF, uuid.uuid4(), ids["project"], survey, version,
                scheduled, scheduled + timedelta(hours=1), label,
                str(uuid.uuid4()),
            ))

        first = create(impl_token)
        patched = state_service().patch(PatchSurveyRound(
            impl_token, CSRF, uuid.uuid4(), ids["project"],
            first.survey_round_id, 0, scheduled + timedelta(days=1),
            scheduled + timedelta(days=1, hours=2), " Updated room ",
        ))
        assert patched.etag == '"v1"' and patched.location_note == "Updated room"
        expect("CONFLICT_VERSION", lambda: state_service().patch(PatchSurveyRound(
            impl_token, CSRF, uuid.uuid4(), ids["project"],
            first.survey_round_id, 0, scheduled, scheduled + timedelta(hours=1),
            "Stale room",
        )))
        expect("RESOURCE_NOT_FOUND", lambda: state_service().patch(PatchSurveyRound(
            customer_token, CSRF, uuid.uuid4(), ids["project"],
            first.survey_round_id, 1, scheduled, scheduled + timedelta(hours=1),
            "Customer room",
        )))

        open_key = str(uuid.uuid4())

        def open_first(_):
            return state_service().open(OpenSurveyRound(
                pm_token, CSRF, uuid.uuid4(), ids["project"],
                first.survey_round_id, 1, open_key,
            ))

        with ThreadPoolExecutor(max_workers=2) as pool:
            opened = list(pool.map(open_first, range(2)))
        assert opened[0] == opened[1]
        assert opened[0].round_state == "OPEN" and opened[0].etag == '"v2"'
        assert opened[0].opened_by == pm and opened[0].opened_at == opened[0].updated_at
        expect("SURVEY_ROUND_STATE_CONFLICT", lambda: state_service().patch(
            PatchSurveyRound(
                impl_token, CSRF, uuid.uuid4(), ids["project"],
                first.survey_round_id, 2, scheduled, scheduled + timedelta(hours=1),
                "Late update",
            )
        ))
        expect("SURVEY_ROUND_STATE_CONFLICT", lambda: state_service().cancel(
            CancelSurveyRound(
                pm_token, CSRF, uuid.uuid4(), ids["project"],
                first.survey_round_id, 2, "Already open", str(uuid.uuid4()),
            )
        ))

        before_close = opened[0]
        close_key = str(uuid.uuid4())
        expect("SURVEY_ROUND_COMPLETENESS_UNAVAILABLE", lambda: state_service().close(
            CloseSurveyRound(
                pm_token, CSRF, uuid.uuid4(), ids["project"],
                first.survey_round_id, 2, close_key,
            )
        ))

        second = create()
        cancel_key = str(uuid.uuid4())
        cancel_command = CancelSurveyRound(
            pm_token, CSRF, uuid.uuid4(), ids["project"],
            second.survey_round_id, 0, " Duplicate interview ", cancel_key,
        )
        cancelled = state_service().cancel(cancel_command)
        replay = state_service().cancel(cancel_command)
        assert cancelled == replay and cancelled.round_state == "CANCELLED"
        assert cancelled.cancellation_reason == "Duplicate interview"
        assert cancelled.cancelled_by == pm
        assert cancelled.cancelled_at == cancelled.updated_at
        expect("SURVEY_ROUND_STATE_CONFLICT", lambda: state_service().open(
            OpenSurveyRound(
                pm_token, CSRF, uuid.uuid4(), ids["project"],
                second.survey_round_id, 1, str(uuid.uuid4()),
            )
        ))

        third = create()
        rollback_key = str(uuid.uuid4())
        failed_command = OpenSurveyRound(
            pm_token, CSRF, uuid.uuid4(), ids["project"],
            third.survey_round_id, 0, rollback_key,
        )
        expect("SURVEY_ROUND_UNAVAILABLE", lambda: state_service(
            FailedAudit(),
        ).open(failed_command))
        recovered = state_service().open(failed_command)
        assert recovered.round_state == "OPEN" and recovered.etag == '"v1"'

        fourth = create()
        expect("AUTH_ACCESS_DENIED", lambda: state_service().open(OpenSurveyRound(
            pm_token, b"x" * 32, uuid.uuid4(), ids["project"],
            fourth.survey_round_id, 0, str(uuid.uuid4()),
        )))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: state_service().open(
            OpenSurveyRound(
                pm_token, CSRF, uuid.uuid4(), ids["project"],
                fourth.survey_round_id, 0, str(uuid.uuid4()),
            )
        ))
        guard.enabled = True

        with connect(database) as db:
            row = db.execute(
                "SELECT round_state,lock_version FROM plm.srv_rounds "
                "WHERE survey_round_id=%s", (first.survey_round_id,),
            ).fetchone()
            assert row == (before_close.round_state, 2)
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_SURVEY_ROUND_CLOSE'",
            ).fetchone()[0] == 0
            actions = dict(db.execute(
                "SELECT action,count(*) FROM plm.aud_events WHERE "
                "target_object_type='SRV-03' AND target_project_id=%s "
                "GROUP BY action", (ids["project"],),
            ).fetchall())
            assert actions["SURVEY_ROUND_CREATED"] == 4
            assert actions["SURVEY_ROUND_PATCHED"] == 1
            assert actions["SURVEY_ROUND_OPENED"] == 2
            assert actions["SURVEY_ROUND_CANCELLED"] == 1
            assert "SURVEY_ROUND_CLOSED" not in actions
            receipts_by_operation = dict(db.execute(
                "SELECT operation,count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation LIKE 'V1_SURVEY_ROUND_%' GROUP BY operation",
            ).fetchall())
            assert receipts_by_operation["V1_SURVEY_ROUND_CREATE"] == 4
            assert receipts_by_operation["V1_SURVEY_ROUND_OPEN"] == 2
            assert receipts_by_operation["V1_SURVEY_ROUND_CANCEL"] == 1
            fourth_row = db.execute(
                "SELECT round_state,lock_version FROM plm.srv_rounds "
                "WHERE survey_round_id=%s", (fourth.survey_round_id,),
            ).fetchone()
            assert fourth_row == ("PLANNED", 0)
        command.check(create_migration_config(url))
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
            )
    print(
        "SUR_02_A05_ROUND_STATE_PASS: PLANNED schedule patch, PM-only concurrent "
        "OPEN, PM-only CANCEL, strong ETag, role/CSRF/License, Audit rollback, "
        "idempotent replay, terminal guards and explicit CLOSE completeness "
        "fail-closed verified on Windows 11/PG18"
    )


if __name__ == "__main__":
    main()
