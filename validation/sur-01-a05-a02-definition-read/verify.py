"""Windows 11/PostgreSQL 18 proof for Survey definition read ownership."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.survey.application.read_surveys import (
    SurveyReadError, SurveyReadQuery, SurveyReadService,
)
from plm_assistant.modules.survey.infrastructure.read_repository import (
    SqlAlchemySurveyReadRepository,
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
    "survey_definition_read_fixture",
)
connect, seed_user, Guard = fixture.connect, fixture.seed_user, fixture.Guard


def expect(code: str, action) -> None:
    try:
        action()
    except SurveyReadError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main() -> None:
    name = "sur01a05a02_" + uuid.uuid4().hex[:8]
    tokens = [bytes([value]) * 32 for value in (112, 105, 109, 99, 102)]
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
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    roles = ("PM", "IM", "CM", "CUSTOMER", "FOREIGN")
                    users = [seed_user(db, "Survey " + role, "NONE", token)
                             for role, token in zip(roles, tokens)]
                    pm, implementer, customer_manager, customer, foreign = users
                    project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('SURREAD','surread','Survey Read',%s) RETURNING project_id",
                        (pm,),
                    ).fetchone()[0]
                    foreign_project = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('SUROTHER','surother','Foreign',%s) RETURNING project_id",
                        (foreign,),
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
                        (customer_manager, "CUSTOMER_MANAGER"),
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

                    fixed = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
                    surveys = [uuid.uuid4() for _ in range(3)]
                    foreign_survey = uuid.uuid4()
                    versions = [uuid.uuid4() for _ in range(3)]
                    question_rows = [uuid.uuid4(), uuid.uuid4()]
                    question_ids = [uuid.uuid4(), uuid.uuid4()]
                    typed = {
                        "handover_item": uuid.uuid4(),
                        "handover_version": uuid.uuid4(),
                        "handover_analysis": uuid.uuid4(),
                        "capability_item": uuid.uuid4(),
                        "capability_version": uuid.uuid4(),
                        "capability_baseline": uuid.uuid4(),
                        "document_version": uuid.uuid4(),
                        "document": uuid.uuid4(),
                    }
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for number, survey_id in enumerate(surveys):
                            db.execute(
                                "INSERT INTO plm.srv_surveys"
                                "(survey_id,project_id,name,survey_state,created_by,"
                                "created_at,updated_at,lock_version) VALUES "
                                "(%s,%s,%s,'ACTIVE',%s,%s,%s,0)",
                                (survey_id, project, f"Survey {number}", pm, fixed, fixed),
                            )
                        db.execute(
                            "INSERT INTO plm.srv_surveys"
                            "(survey_id,project_id,name,survey_state,created_by,"
                            "created_at,updated_at,lock_version) VALUES "
                            "(%s,%s,'Foreign','ACTIVE',%s,%s,%s,0)",
                            (foreign_survey, foreign_project, foreign, fixed, fixed),
                        )
                        for number, version_id in enumerate(versions, 1):
                            detail_counts = (2, 1, 5, 1) if number == 3 else (1, 0, 1, 1)
                            db.execute(
                                "INSERT INTO plm.srv_survey_versions"
                                "(survey_version_id,survey_id,project_id,version_no,"
                                "version_state,content_fingerprint,declared_question_count,"
                                "declared_option_count,declared_source_count,"
                                "declared_target_department_count,created_by,created_at) "
                                "VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s)",
                                (version_id, surveys[0], project, number,
                                 bytes([number]) * 32, *detail_counts, pm, fixed),
                            )
                        db.execute(
                            "INSERT INTO plm.srv_questions"
                            "(question_row_id,survey_version_id,survey_id,project_id,"
                            "question_id,sequence_no,topic,question_text,objective,"
                            "answer_type,validation_rule,required,condition_rule,"
                            "expected_output,evidence_required) VALUES "
                            "(%s,%s,%s,%s,%s,0,'Scope','Choose scope','Confirm scope',"
                            "'SINGLE_CHOICE','{}'::jsonb,true,NULL,'Chosen scope',false),"
                            "(%s,%s,%s,%s,%s,1,'Detail','Describe detail','Capture detail',"
                            "'TEXT','{\"max_length\":1000}'::jsonb,false,"
                            "'{\"question_ref\":\"placeholder\"}'::jsonb,"
                            "'Detail text',true)",
                            (question_rows[0], versions[2], surveys[0], project,
                             question_ids[0], question_rows[1], versions[2],
                             surveys[0], project, question_ids[1]),
                        )
                        db.execute(
                            "INSERT INTO plm.srv_question_options"
                            "(question_option_id,question_row_id,survey_version_id,"
                            "survey_id,project_id,option_code,label,ordinal) "
                            "VALUES (%s,%s,%s,%s,%s,'A','Option A',0)",
                            (uuid.uuid4(), question_rows[0], versions[2], surveys[0], project),
                        )
                        source_sql = (
                            "INSERT INTO plm.srv_question_source_refs"
                            "(question_source_ref_id,question_row_id,survey_version_id,"
                            "survey_id,project_id,source_kind,handover_item_row_id,"
                            "handover_analysis_version_id,handover_analysis_id,"
                            "capability_item_row_id,capability_baseline_version_id,"
                            "capability_baseline_id,template_document_version_id,"
                            "template_document_id,manual_source_note,ordinal) VALUES "
                            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                        )
                        source_values = (
                            ("HANDOVER_ITEM", typed["handover_item"],
                             typed["handover_version"], typed["handover_analysis"],
                             None, None, None, None, None, None),
                            ("CAPABILITY_ITEM", None, None, None,
                             typed["capability_item"], typed["capability_version"],
                             typed["capability_baseline"], None, None, None),
                            ("TEMPLATE_DOCUMENT_VERSION", None, None, None,
                             None, None, None, typed["document_version"],
                             typed["document"], None),
                            ("MANUAL", None, None, None, None, None, None, None,
                             None, "Face-to-face customer record"),
                        )
                        for ordinal, values in enumerate(source_values):
                            db.execute(source_sql, (
                                uuid.uuid4(), question_rows[0], versions[2],
                                surveys[0], project, values[0], *values[1:], ordinal,
                            ))
                        db.execute(source_sql, (
                            uuid.uuid4(), question_rows[1], versions[2], surveys[0],
                            project, "MANUAL", None, None, None, None, None, None,
                            None, None, "Observed process", 0,
                        ))
                        db.execute(
                            "INSERT INTO plm.srv_target_departments"
                            "(survey_target_department_ref_id,survey_version_id,"
                            "survey_id,project_id,department_id,ordinal) "
                            "VALUES (%s,%s,%s,%s,%s,0)",
                            (uuid.uuid4(), versions[2], surveys[0], project, department),
                        )
                    before = db.execute(
                        "SELECT (SELECT count(*) FROM plm.aud_events),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                        "(SELECT count(*) FROM plm.srv_surveys),"
                        "(SELECT count(*) FROM plm.srv_survey_versions),"
                        "(SELECT count(*) FROM plm.srv_questions)"
                    ).fetchone()

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )

                def service(custom_guard=None):
                    return SurveyReadService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectReadAccess(),
                        license_guard=custom_guard or guard,
                        authorization=authorization,
                        repository=SqlAlchemySurveyReadRepository(),
                    )

                def query(index: int, selected_project=project):
                    return SurveyReadQuery(tokens[index], uuid.uuid4(), selected_project)

                for index in range(4):
                    first = service().list_surveys(query(index), page_size=2)
                    assert len(first.items) == 2 and first.has_more
                    second = service().list_surveys(
                        query(index), page_size=2,
                        after_updated_at=first.next_updated_at,
                        after_survey_id=first.next_survey_id,
                    )
                    assert len(second.items) == 1 and not second.has_more
                    assert len({item.survey_id for item in first.items + second.items}) == 3
                root = service().get_survey(query(0), surveys[0])
                assert root.etag == '"v0"' and root.project_id == project
                first_versions = service().list_versions(
                    query(0), survey_id=surveys[0], page_size=2,
                )
                assert [item.version_no for item in first_versions.items] == [3, 2]
                tail_versions = service().list_versions(
                    query(0), survey_id=surveys[0], page_size=2,
                    after_version_no=first_versions.next_version_no,
                )
                assert [item.version_no for item in tail_versions.items] == [1]
                detail = service().get_version(
                    query(0), survey_id=surveys[0], survey_version_id=versions[2],
                )
                assert detail.content_fingerprint == (bytes([3]) * 32).hex()
                assert [question.sequence_no for question in detail.questions] == [0, 1]
                assert len(detail.questions[0].options) == 1
                assert {source.source_kind for source in detail.questions[0].sources} == {
                    "HANDOVER_ITEM", "CAPABILITY_ITEM",
                    "TEMPLATE_DOCUMENT_VERSION", "MANUAL",
                }
                assert detail.questions[0].sources[0].handover_item_row_id == typed["handover_item"]
                assert detail.questions[0].sources[2].template_document_id == typed["document"]
                assert detail.target_departments[0].department_id == department
                assert not hasattr(detail.questions[0].sources[2], "storage_locator")
                expect("RESOURCE_NOT_FOUND", lambda: service().get_survey(
                    query(0), foreign_survey,
                ))
                expect("RESOURCE_NOT_FOUND", lambda: service().list_surveys(
                    query(4), page_size=10,
                ))
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s",
                        (project,),
                    )
                assert len(service().list_surveys(query(0), page_size=10).items) == 3
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s",
                        (project,),
                    )
                    db.execute(
                        "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                        "WHERE project_id=%s AND user_id=%s", (project, customer),
                    )
                expect("RESOURCE_NOT_FOUND", lambda: service().list_surveys(
                    query(3), page_size=10,
                ))
                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(expired).get_survey(
                    query(0), surveys[0],
                ))
                with connect(name) as db:
                    after = db.execute(
                        "SELECT (SELECT count(*) FROM plm.aud_events),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                        "(SELECT count(*) FROM plm.srv_surveys),"
                        "(SELECT count(*) FROM plm.srv_survey_versions),"
                        "(SELECT count(*) FROM plm.srv_questions)"
                    ).fetchone()
                    assert before == after, (before, after)
                print(
                    "SUR_01_A05_A02_DEFINITION_READ_OWNER_PASS: four-role current "
                    "membership, tied-timestamp Survey keyset, descending Version "
                    "pagination, complete bounded typed-reference projection, cross-project/"
                    "revoked/License denial, archived reads and zero writes verified on "
                    "PostgreSQL 18"
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
