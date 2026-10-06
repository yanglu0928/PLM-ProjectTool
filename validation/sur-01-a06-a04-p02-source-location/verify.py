"""Windows 11/PostgreSQL 18.6 proof for internal Survey source locations."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.capability.infrastructure.survey_source_location import (
    SqlAlchemyCapabilitySurveySourceLocation,
)
from plm_assistant.modules.document.infrastructure.survey_source_location import (
    SqlAlchemyDocumentSurveySourceLocation,
)
from plm_assistant.modules.handover.infrastructure.survey_source_location import (
    SqlAlchemyHandoverSurveySourceLocation,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.survey.application.source_location import (
    SurveySourceLocationQuery, SurveySourceLocationService,
)
from plm_assistant.modules.survey.infrastructure.read_repository import (
    SqlAlchemySurveyReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"
))
helpers = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, seed_dependencies, insert_valid = (
    schema["connect"], schema["seed_dependencies"], schema["insert_valid"],
)
seed_user, Guard = helpers["seed_user"], helpers["Guard"]


def main() -> None:
    database = "sur01a06a04p02_" + uuid.uuid4().hex[:8]
    token = b"l" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = seed_dependencies(db)
            actor = seed_user(db, "Survey locator reader", "NONE", token)
            db.execute("""
                INSERT INTO plm.prj_project_members(
                  project_id,user_id,department_id,project_role)
                VALUES (%s,%s,%s,'CUSTOMER_MEMBER')
            """, (ids["project"], actor, ids["department"]))
            survey, version = insert_valid(db, ids)
            questions = tuple(row[0] for row in db.execute("""
                SELECT question_id FROM plm.srv_questions
                WHERE survey_version_id=%s ORDER BY sequence_no
            """, (version,)).fetchall())
            before = db.execute("""
                SELECT (SELECT count(*) FROM plm.srv_surveys),
                       (SELECT count(*) FROM plm.srv_survey_versions),
                       (SELECT count(*) FROM plm.aud_events)
            """).fetchone()
        runtime = create_database_runtime(url)
        try:
            service = SurveySourceLocationService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectReadAccess(), license_guard=Guard(),
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                sources=SqlAlchemySurveyReadRepository(),
                handover=SqlAlchemyHandoverSurveySourceLocation(),
                capability=SqlAlchemyCapabilitySurveySourceLocation(),
                documents=SqlAlchemyDocumentSurveySourceLocation(),
                clock=lambda: datetime.now(timezone.utc),
            )
            query = SurveySourceLocationQuery(token, uuid.uuid4(), ids["project"])
            with runtime.unit_of_work() as tx:
                probe_source = SqlAlchemySurveyReadRepository().get_source(
                    tx, project_id=ids["project"], survey_id=survey,
                    survey_version_id=version, question_id=questions[0],
                    source_ordinal=0,
                )
                assert probe_source is not None
                probe_target = SqlAlchemyHandoverSurveySourceLocation().resolve(
                    tx, project_id=ids["project"],
                    analysis_item_row_id=ids["handover_item_row"],
                    handover_analysis_version_id=ids["analysis_version"],
                    handover_analysis_id=ids["analysis"],
                )
                assert probe_target is not None
                assert SurveySourceLocationService._handover_view(
                    probe_source, ids["project"], probe_target,
                ).resolution_state == "LOCATABLE"
                access = SqlAlchemyProjectReadAccess()
                assert access.authenticated_user(
                    tx, session_token=token, now=datetime.now(timezone.utc),
                ) == actor
                ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ).require_in_transaction(
                    tx, user_id=actor, project_id=ids["project"],
                    operation="SURVEY_VERSION_GET",
                )
            resolved = []
            for index, question in enumerate(questions):
                try:
                    resolved.append(service.locate(
                        query, survey_id=survey, survey_version_id=version,
                        question_id=question, source_ordinal=0,
                    ))
                except Exception as error:
                    raise AssertionError(f"source location failed at index {index}") from error
            results = tuple(resolved)
            assert tuple(value.source_kind for value in results) == (
                "HANDOVER_ITEM", "CAPABILITY_ITEM",
                "TEMPLATE_DOCUMENT_VERSION", "MANUAL",
            )
            assert results[0].resolution_state == "LOCATABLE"
            assert results[0].record_ref.item_id == ids["handover_item"]
            assert results[0].current_eligibility is True
            assert results[1].resolution_state == "PARTIALLY_LOCATABLE"
            assert results[1].record_ref.item_id == ids["capability_item"]
            assert results[1].locations == ()
            assert results[2].resolution_state == "PARTIALLY_LOCATABLE"
            assert results[2].locations == ()  # GLOBAL does not inherit Project access.
            assert results[3].unavailable_reason == "MANUAL_SOURCE_NOT_FIXED"

            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.hnd_analyses SET analysis_state='RESTRICTED' "
                           "WHERE handover_analysis_id=%s", (ids["analysis"],))
                db.execute("UPDATE plm.cap_baselines SET baseline_state='RESTRICTED' "
                           "WHERE baseline_id=%s", (ids["baseline"],))
            handover = service.locate(
                query, survey_id=survey, survey_version_id=version,
                question_id=questions[0], source_ordinal=0,
            )
            capability = service.locate(
                query, survey_id=survey, survey_version_id=version,
                question_id=questions[1], source_ordinal=0,
            )
            assert handover.resolution_state == "LOCATABLE"
            assert handover.current_eligibility is False
            assert capability.resolution_state == "PARTIALLY_LOCATABLE"
            assert capability.current_eligibility is False
            with connect(database) as db:
                after = db.execute("""
                    SELECT (SELECT count(*) FROM plm.srv_surveys),
                           (SELECT count(*) FROM plm.srv_survey_versions),
                           (SELECT count(*) FROM plm.aud_events)
                """).fetchone()
                assert after == before, (before, after)
            print(
                "SUR_01_A06_A04_P02_SOURCE_LOCATION_INTERNAL_PASS: exact four-kind "
                "Survey source resolution, public refs, GLOBAL withholding, historical/current "
                "separation and zero-write behavior verified on Windows 11/PostgreSQL 18.6"
            )
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()

