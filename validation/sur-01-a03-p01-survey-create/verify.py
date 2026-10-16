"""Windows 11/PostgreSQL 18 proof for Survey identity creation."""

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
from plm_assistant.modules.survey.application.create_survey import (
    CreateSurvey, SurveyCreateError, SurveyCreateService,
)
from plm_assistant.modules.survey.infrastructure.survey_create_repository import (
    SqlAlchemySurveyCreateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]


def expect(code: str, action) -> None:
    try:
        action()
    except SurveyCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "sur01a03p01_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "Survey PM", "NONE", pm_token)
                    impl = seed_user(db, "Survey Implementer", "NONE", impl_token)
                    customer = seed_user(db, "Survey Customer", "NONE", customer_token)
                    project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                        "name,created_by) VALUES ('SURP01','surp01','Survey Project',%s) "
                        "RETURNING project_id", (pm,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,"
                        "department_code_normalized,name) VALUES (%s,'BUS','bus','Business') "
                        "RETURNING department_id", (project,),
                    ).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"),
                                       (impl, "IMPLEMENTATION_MEMBER"),
                                       (customer, "CUSTOMER_MANAGER")):
                        db.execute(
                            "INSERT INTO plm.prj_project_members(project_id,user_id,"
                            "department_id,project_role) VALUES (%s,%s,%s,%s)",
                            (project, user, department, role),
                        )

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                common = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                    authorization=authorization,
                    repository=SqlAlchemySurveyCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def service(audit=None):
                    return SurveyCreateService(
                        **common, audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    )

                def create(*, token=pm_token, csrf=CSRF,
                           survey_name="Business discovery", key=None, target=None):
                    return (target or service()).create(CreateSurvey(
                        token, csrf, uuid.uuid4(), project, survey_name,
                        key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                expect("RESOURCE_NOT_FOUND", lambda: create(token=customer_token))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", create)
                guard.enabled = True

                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(
                    key=first_key, survey_name="Changed discovery",
                ))
                implemented = create(
                    token=impl_token, survey_name="Implementation discovery",
                )
                assert implemented.project_id == project

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: create(
                        key=concurrent_key, survey_name="Concurrent discovery",
                    ), range(2)))
                assert results[0] == results[1]

                rollback_key = str(uuid.uuid4())
                expect("SURVEY_UNAVAILABLE", lambda: create(
                    key=rollback_key, survey_name="Rollback discovery",
                    target=service(FailedAudit()),
                ))
                recovered = create(
                    key=rollback_key, survey_name="Rollback discovery",
                )
                assert recovered.survey_id not in {
                    first.survey_id, implemented.survey_id, results[0].survey_id,
                }

                with connect(name) as db:
                    row = db.execute(
                        "SELECT project_id,name,survey_state,current_approved_version_ref,"
                        "lock_version FROM plm.srv_surveys WHERE survey_id=%s",
                        (first.survey_id,),
                    ).fetchone()
                    assert row == (
                        project, "Business discovery", "ACTIVE", None, 0,
                    ), row
                    assert db.execute(
                        "SELECT count(*) FROM plm.srv_survey_versions"
                    ).fetchone()[0] == 0
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE "
                        "action='SURVEY_CREATED' AND target_object_id=%s",
                        (first.survey_id,),
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                        "operation='V1_SURVEY_CREATE'"
                    ).fetchone()[0] == 4
                    db.execute(
                        "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                        "WHERE project_id=%s AND user_id=%s", (project, pm),
                    )
                expect("RESOURCE_NOT_FOUND", lambda: create(key=first_key))
                print(
                    "SUR_01_A03_P01_SURVEY_CREATE_PASS: PM/Implementation role, "
                    "Session/CSRF/License, replay/concurrency, Audit rollback, "
                    "zero-Version boundary and role revocation verified on PostgreSQL 18"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
