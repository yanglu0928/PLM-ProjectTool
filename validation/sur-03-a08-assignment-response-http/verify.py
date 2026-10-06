"""Windows 11/PostgreSQL 18 proof for Assignment/Response frozen HTTP chain."""

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
    SURVEY_CURSOR_KEY_REF,
    SURVEY_VERSION_CURSOR_KEY_REF,
    create_windows_survey_routers,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"))
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, definition = schema["connect"], schema["load_definition_fixture"]()
approve_definition = schema["approve_definition"]
seed_user, Guard, CSRF = auth["seed_user"], auth["Guard"], auth["CSRF"]


class Keys:
    def resolve_key(self, key_ref):
        return {
            SURVEY_CURSOR_KEY_REF: b"s" * 32,
            SURVEY_VERSION_CURSOR_KEY_REF: b"v" * 32,
        }.get(key_ref)


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"p" * 32:
            raise ValueError()
        return object()


def headers(*, key=None, match=None):
    value = {
        "origin": "http://localhost",
        "cookie": "plm_session=" + (b"p" * 32).hex(),
        "x-csrf-token": CSRF.hex(),
    }
    if key is not None:
        value["idempotency-key"] = key
    if match is not None:
        value["if-match"] = match
    return value


def main():
    database = "sur03a08_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            actor = seed_user(db, "Assignment HTTP PM", "NONE", b"p" * 32)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,"
                       "department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                       (ids["project"], actor, ids["department"]))
            survey, version = definition.insert_valid(
                db, ids, name="Assignment HTTP survey")
            approve_definition(db, ids, survey, version)
            questions = db.execute(
                "SELECT question_id,answer_type FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no", (version,)
            ).fetchall()
            round_id = uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("INSERT INTO plm.srv_rounds(survey_round_id,survey_id,"
                           "survey_version_id,project_id,round_no,round_state,opened_by,"
                           "opened_at,created_by,updated_by,lock_version) VALUES "
                           "(%s,%s,%s,%s,1,'OPEN',%s,statement_timestamp(),%s,%s,1)",
                           (round_id, survey, version, ids["project"], actor, actor, actor))

        runtime = create_database_runtime(url)
        guard = Guard()
        guard.enabled = True
        routers = create_windows_survey_routers(
            runtime, sessions=Sessions(),
            origins=LoginOriginPolicy(["http://localhost"]),
            license_guard=guard, audit=AuditService(SqlAlchemyAuditRepository()),
            include_write=True, resolver=Keys(), documents=object(),
            downloads=object(), parse_results=object(),
        )
        app = create_app(survey_read_router=routers.reads,
                         survey_command_router=routers.commands)
        root = (f"/api/v1/projects/{ids['project']}/survey-rounds/"
                f"{round_id}/assignments")

        with TestClient(app, base_url="http://localhost") as client:
            def create_assignment(assignee):
                response = client.post(root, headers=headers(key=str(uuid.uuid4())),
                    json={"department_id": str(ids["department"]),
                          "assignee_user_id": (None if assignee is None
                                               else str(assignee))})
                assert response.status_code == 201, response.text
                return response.json()["data"]["survey_assignment_id"]

            def answer_all(assignment_id):
                etag = '"v0"'
                for question_id, answer_type in questions:
                    answer_value = "YES" if answer_type == "SINGLE_CHOICE" else "answer"
                    response = client.post(
                        f"{root}/{assignment_id}/responses",
                        headers=headers(key=str(uuid.uuid4()), match=etag),
                        json={
                            "question_id": str(question_id),
                            "response_source": "SELF_SERVICE",
                            "raw_answer": answer_value,
                            "answer_value": answer_value,
                            "evidence_ids": [],
                            "project_record_evidence_id": None,
                            "correction_of_response_id": None,
                        },
                    )
                    assert response.status_code == 201, response.text
                    etag = response.headers["etag"]
                return etag

            validated_id = create_assignment(actor)
            returned_id = create_assignment(None)
            etag = answer_all(validated_id)
            submitted = client.post(
                f"{root}/{validated_id}:submit",
                headers=headers(key=str(uuid.uuid4()), match=etag), content=b"")
            assert submitted.status_code == 200, submitted.text
            validated = client.post(
                f"{root}/{validated_id}:validate",
                headers=headers(key=str(uuid.uuid4()),
                                match=submitted.headers["etag"]), content=b"")
            assert validated.status_code == 200, validated.text
            assert validated.json()["data"]["state"] == "VALIDATED"

            etag = answer_all(returned_id)
            submitted = client.post(
                f"{root}/{returned_id}:submit",
                headers=headers(key=str(uuid.uuid4()), match=etag), content=b"")
            assert submitted.status_code == 200, submitted.text
            returned = client.post(
                f"{root}/{returned_id}:return",
                headers=headers(key=str(uuid.uuid4()),
                                match=submitted.headers["etag"]),
                json={"comment": "Please clarify scope"})
            assert returned.status_code == 200, returned.text
            assert returned.json()["data"]["state"] == "RETURNED"

            listing = client.get(root + "?page_size=1", headers=headers())
            assert listing.status_code == 200, listing.text
            assert listing.json()["data"]["has_more"] is True
            cursor = listing.json()["data"]["next_cursor"]
            assert client.get(root + f"?page_size=1&cursor={cursor}",
                              headers=headers()).status_code == 200
            detail = client.get(f"{root}/{validated_id}", headers=headers())
            assert detail.status_code == 200, detail.text
            assert detail.headers["etag"] == '"v6"'
            assert detail.json()["data"]["response_count"] == 4
            assert len(detail.json()["data"]["responses"]) == 4
            assert client.get(root + "?page_size=2&cursor=" + cursor,
                              headers=headers()).status_code == 400

        with connect(database) as db:
            states = db.execute(
                "SELECT submission_state,count(*) FROM plm.srv_assignments "
                "GROUP BY submission_state ORDER BY submission_state").fetchall()
            assert states == [("RETURNED", 1), ("VALIDATED", 1)], states
            assert db.execute("SELECT count(*) FROM plm.srv_responses").fetchone()[0] == 8
            assert db.execute("SELECT count(*) FROM plm.srv_answers").fetchone()[0] == 8
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action IN ("
                              "'SURVEY_ASSIGNMENT_CREATED','SURVEY_RESPONSE_RECORDED',"
                              "'SURVEY_ASSIGNMENT_SUBMITTED','SURVEY_ASSIGNMENT_VALIDATED',"
                              "'SURVEY_ASSIGNMENT_RETURNED')").fetchone()[0] == 14
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                              "operation LIKE 'V1_SURVEY_%'").fetchone()[0] == 14
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print("SUR_03_A08_ASSIGNMENT_RESPONSE_HTTP_PASS: seven frozen operations, signed cursor binding, response detail projection, 14 atomic writes/Audit/receipts and Alembic drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__":
    main()
