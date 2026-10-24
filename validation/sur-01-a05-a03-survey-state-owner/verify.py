"""Windows 11/PostgreSQL 18 proof for Survey metadata/archive Owner."""

from __future__ import annotations

import importlib.util
import uuid
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
from plm_assistant.modules.survey.application.change_survey import (
    ArchiveSurvey, PatchSurvey, SurveyStateError, SurveyStateService,
)
from plm_assistant.modules.survey.infrastructure.state_repository import (
    SqlAlchemySurveyStateRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py",
    "survey_state_fixture",
)
connect, seed_user = fixture.connect, fixture.seed_user
Guard, CSRF = fixture.Guard, fixture.CSRF


def expect(code: str, action) -> None:
    try:
        action()
    except SurveyStateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


class FailedAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def main() -> None:
    name = "sur01a05a03_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token, foreign_token = (
        bytes([value]) * 32 for value in (112, 105, 99, 102)
    )
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20261006_0105")
            command.upgrade(config, "head")
            command.check(config)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "Survey State PM", "NONE", pm_token)
                    implementer = seed_user(db, "Survey State IM", "NONE", impl_token)
                    customer = seed_user(db, "Survey State Customer", "NONE", customer_token)
                    foreign = seed_user(db, "Survey State Foreign", "NONE", foreign_token)
                    project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('SURSTATE','surstate','Survey State',%s) "
                        "RETURNING project_id", (pm,),
                    ).fetchone()[0]
                    foreign_project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('SURSTATE2','surstate2','Foreign',%s) "
                        "RETURNING project_id", (foreign,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments"
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'SUR','sur','Survey') RETURNING department_id",
                        (project,),
                    ).fetchone()[0]
                    foreign_department = db.execute(
                        "INSERT INTO plm.prj_departments"
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'SUR','sur','Foreign') RETURNING department_id",
                        (foreign_project,),
                    ).fetchone()[0]
                    for user, role in (
                        (pm, "PROJECT_MANAGER"),
                        (implementer, "IMPLEMENTATION_MEMBER"),
                        (customer, "CUSTOMER_MEMBER"),
                    ):
                        db.execute(
                            "INSERT INTO plm.prj_project_members"
                            "(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,%s)",
                            (project, user, department, role),
                        )
                    db.execute(
                        "INSERT INTO plm.prj_project_members"
                        "(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                        (foreign_project, foreign, foreign_department),
                    )
                    surveys = [uuid.uuid4() for _ in range(5)]
                    foreign_survey = uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for index, survey_id in enumerate(surveys):
                            db.execute(
                                "INSERT INTO plm.srv_surveys"
                                "(survey_id,project_id,name,survey_state,created_by,"
                                "lock_version) VALUES (%s,%s,%s,'ACTIVE',%s,0)",
                                (survey_id, project, f"Survey {index}", pm),
                            )
                        db.execute(
                            "INSERT INTO plm.srv_surveys"
                            "(survey_id,project_id,name,survey_state,created_by,"
                            "lock_version) VALUES (%s,%s,'Foreign','ACTIVE',%s,0)",
                            (foreign_survey, foreign_project, foreign),
                        )
                        db.execute(
                            "INSERT INTO plm.srv_survey_versions"
                            "(survey_version_id,survey_id,project_id,version_no,"
                            "version_state,content_fingerprint,declared_question_count,"
                            "declared_option_count,declared_source_count,"
                            "declared_target_department_count,review_ref,"
                            "review_round_ref,created_by) VALUES "
                            "(%s,%s,%s,1,'IN_REVIEW',%s,1,0,1,1,%s,%s,%s)",
                            (uuid.uuid4(), surveys[3], project, b"v" * 32,
                             uuid.uuid4(), uuid.uuid4(), pm),
                        )

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )

                def service(custom_guard=None, audit=None):
                    return SurveyStateService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectWriteAccess(),
                        license_guard=custom_guard or guard,
                        authorization=authorization,
                        repository=SqlAlchemySurveyStateRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    )

                def patch(token, survey_id, expected, name_value,
                          selected_project=project):
                    return PatchSurvey(
                        token, CSRF, uuid.uuid4(), selected_project,
                        survey_id, expected, name_value,
                    )

                def archive(token, survey_id, expected, key,
                            selected_project=project):
                    return ArchiveSurvey(
                        token, CSRF, uuid.uuid4(), selected_project,
                        survey_id, expected, key,
                    )

                pm_result = service().patch(patch(
                    pm_token, surveys[0], 0, "  Ｔｅｃｈｎｉｃａｌ survey  ",
                ))
                assert (pm_result.name, pm_result.etag) == (
                    "Technical survey", '"v1"',
                )
                impl_result = service().patch(patch(
                    impl_token, surveys[1], 0, "Implementation survey",
                ))
                assert impl_result.etag == '"v1"'
                expect("RESOURCE_NOT_FOUND", lambda: service().patch(patch(
                    customer_token, surveys[2], 0, "Customer attempt",
                )))
                expect("CONFLICT_VERSION", lambda: service().patch(patch(
                    pm_token, surveys[0], 0, "Stale",
                )))
                expect("RESOURCE_NOT_FOUND", lambda: service().patch(patch(
                    pm_token, foreign_survey, 0, "Cross project",
                )))
                expect("SURVEY_STATE_CONFLICT", lambda: service().patch(patch(
                    pm_token, surveys[3], 0, "Review drift",
                )))
                expect("SURVEY_STATE_CONFLICT", lambda: service().archive(archive(
                    pm_token, surveys[3], 0, str(uuid.uuid4()),
                )))
                archive_key = str(uuid.uuid4())
                archived = service().archive(archive(
                    pm_token, surveys[0], 1, archive_key,
                ))
                replayed = service().archive(archive(
                    pm_token, surveys[0], 1, archive_key,
                ))
                assert archived == replayed
                assert (archived.survey_state, archived.etag) == ("ARCHIVED", '"v2"')
                expect("RESOURCE_NOT_FOUND", lambda: service().archive(archive(
                    impl_token, surveys[1], 1, str(uuid.uuid4()),
                )))
                expect("SURVEY_STATE_CONFLICT", lambda: service().patch(patch(
                    pm_token, surveys[0], 2, "Cannot restore",
                )))
                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(expired).patch(patch(
                    pm_token, surveys[2], 0, "License denied",
                )))
                expect("SURVEY_UNAVAILABLE", lambda: service(
                    audit=AuditService(FailedAudit()),
                ).patch(patch(pm_token, surveys[4], 0, "Must roll back")))

                with connect(name) as db:
                    rolled_back = db.execute(
                        "SELECT name,lock_version FROM plm.srv_surveys "
                        "WHERE survey_id=%s", (surveys[4],),
                    ).fetchone()
                    assert rolled_back == ("Survey 4", 0), rolled_back
                    audit_counts = dict(db.execute(
                        "SELECT action,count(*) FROM plm.aud_events "
                        "WHERE target_owner_module='survey' AND action IN "
                        "('SURVEY_PATCHED','SURVEY_ARCHIVED') GROUP BY action"
                    ).fetchall())
                    assert audit_counts == {
                        "SURVEY_PATCHED": 2,
                        "SURVEY_ARCHIVED": 1,
                    }, audit_counts
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_SURVEY_ARCHIVE'"
                    ).fetchone()[0] == 1
                    try:
                        db.execute(
                            "UPDATE plm.srv_surveys SET name='Bypass',updated_by=%s,"
                            "updated_at=statement_timestamp(),lock_version=lock_version+1 "
                            "WHERE survey_id=%s", (pm, surveys[0]),
                        )
                    except Exception:
                        db.rollback()
                    else:
                        raise AssertionError("archived Survey accepted metadata write")

                try:
                    command.downgrade(config, "20261006_0105")
                except Exception as error:
                    assert "state-owner history prevents downgrade" in str(error)
                else:
                    raise AssertionError("state-owner history downgrade was accepted")
                print(
                    "SUR_01_A05_A03_SURVEY_STATE_OWNER_PASS: migration roundtrip, "
                    "narrow metadata/archive guard, PM/implementer roles, project "
                    "isolation, strong version, Review fence, exact archive replay, "
                    "License/audit rollback, archived write rejection and historical "
                    "downgrade refusal verified on PostgreSQL 18"
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
