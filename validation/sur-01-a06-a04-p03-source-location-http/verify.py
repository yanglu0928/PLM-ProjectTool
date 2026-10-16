"""Windows 11/PostgreSQL 18.6 HTTP proof for Survey source locations."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_survey import (
    SURVEY_CURSOR_KEY_REF, SURVEY_VERSION_CURSOR_KEY_REF,
    create_windows_survey_routers,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


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
TOKEN = b"l" * 32


class Keys:
    def resolve_key(self, key_ref: str) -> bytes | None:
        return {SURVEY_CURSOR_KEY_REF: b"s" * 32,
                SURVEY_VERSION_CURSOR_KEY_REF: b"v" * 32}.get(key_ref)


class Sessions:
    @staticmethod
    def validate(token, **kwargs):
        if token != TOKEN:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers() -> dict[str, str]:
    return {"origin": "http://localhost",
            "cookie": "plm_session=" + TOKEN.hex()}


def expect(client: TestClient, path: str, status: int = 200) -> dict[str, object]:
    response = client.get(path, headers=headers())
    if response.status_code != status:
        raise AssertionError((path, response.status_code, response.text))
    return response.json().get("data", {})


def main() -> None:
    database = "sur01a06a04p03_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            actor = seed_user(db, "Survey source location reader", "NONE", TOKEN)
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
            routers = create_windows_survey_routers(
                runtime, sessions=Sessions(),
                origins=LoginOriginPolicy(["http://localhost"]),
                license_guard=Guard(), audit=object(), include_write=False,
                resolver=Keys(),
            )
            app = create_app(survey_read_router=routers.reads)
            base = (f"/api/v1/projects/{ids['project']}/surveys/{survey}"
                    f"/versions/{version}/questions")
            paths = [f"{base}/{question}/sources/0/location"
                     for question in questions]
            with TestClient(create_app(), base_url="http://localhost") as bare:
                assert bare.get(paths[0], headers=headers()).status_code == 404
            with TestClient(app, base_url="http://localhost") as client:
                results = tuple(expect(client, path) for path in paths)
                assert tuple(result["source_kind"] for result in results) == (
                    "HANDOVER_ITEM", "CAPABILITY_ITEM",
                    "TEMPLATE_DOCUMENT_VERSION", "MANUAL",
                )
                assert results[0]["resolution_state"] == "LOCATABLE"
                assert results[0]["current_eligibility"] is True
                assert results[0]["record_ref"]["analysis_item_id"] == str(
                    ids["handover_item"])
                location_kinds = tuple(item["location_kind"]
                                       for item in results[0]["locations"])
                assert location_kinds[0] == "BUSINESS_RECORD"
                assert all(kind == "EVIDENCE" for kind in location_kinds[1:])
                assert "row_id" not in str(results[0]).lower()
                assert results[1]["resolution_state"] == "PARTIALLY_LOCATABLE"
                assert results[1]["locations"] == []
                assert results[1]["unavailable_reason"] == "NO_AUTHORIZED_LOCATION"
                assert results[2]["resolution_state"] == "PARTIALLY_LOCATABLE"
                assert results[2]["locations"] == []
                assert results[3]["unavailable_reason"] == "MANUAL_SOURCE_NOT_FIXED"
                assert client.get(paths[0] + "?expand=content",
                                  headers=headers()).status_code == 400
                assert client.get(paths[0].replace("/sources/0/", "/sources/00/"),
                                  headers=headers()).status_code == 422
                unknown = paths[0].replace(str(questions[0]), str(uuid.uuid4()))
                assert client.get(unknown, headers=headers()).status_code == 404
                foreign = paths[0].replace(str(ids["project"]), str(uuid.uuid4()))
                assert client.get(foreign, headers=headers()).status_code == 404

                with connect(database) as db, db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "UPDATE plm.hnd_analyses SET analysis_state='RESTRICTED' "
                        "WHERE handover_analysis_id=%s", (ids["analysis"],))
                drifted = expect(client, paths[0])
                assert drifted["resolution_state"] == "LOCATABLE"
                assert drifted["current_eligibility"] is False

            with connect(database) as db:
                after = db.execute("""
                    SELECT (SELECT count(*) FROM plm.srv_surveys),
                           (SELECT count(*) FROM plm.srv_survey_versions),
                           (SELECT count(*) FROM plm.aud_events)
                """).fetchone()
                assert after == before, (before, after)
            command.check(cfg)
            print(
                "SUR_01_A06_A04_P03_SOURCE_LOCATION_HTTP_PASS: strict source "
                "location HTTP, Windows read composition, four source kinds, public "
                "projection, drift, isolation and zero-write behavior verified on "
                "Windows 11/PostgreSQL 18.6"
            )
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
