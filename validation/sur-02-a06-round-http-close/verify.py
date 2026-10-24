"""Windows 11/PostgreSQL 18 proof for Round HTTP and atomic CLOSE."""

from __future__ import annotations

import io
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
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.document.application.prepare_download import VerifiedDownload
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"))
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, definition = schema["connect"], schema["load_definition_fixture"]()
approve_definition, insert_evidence = schema["approve_definition"], schema["insert_evidence"]
seed_user, Guard, CSRF = auth["seed_user"], auth["Guard"], auth["CSRF"]


class Keys:
    def resolve_key(self, key_ref):
        return {SURVEY_CURSOR_KEY_REF: b"s" * 32,
                SURVEY_VERSION_CURSOR_KEY_REF: b"v" * 32}.get(key_ref)


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"p" * 32:
            raise ValueError()
        return object()


class Documents:
    def __init__(self, facts): self.facts = facts
    def get_source_facts_for_evidence(self, *args): return self.facts


class Downloads:
    def __init__(self, version, fingerprint):
        self.version, self.fingerprint = version, fingerprint
    def prepare(self, *args):
        return VerifiedDownload(
            self.version, 0, "application/pdf", self.fingerprint, io.BytesIO())


def headers(*, key=None, match='"v1"'):
    value = {
        "origin": "http://localhost",
        "cookie": "plm_session=" + (b"p" * 32).hex(),
        "x-csrf-token": CSRF.hex(), "if-match": match,
    }
    if key is not None: value["idempotency-key"] = key
    return value


def main():
    database = "sur02a06_" + uuid.uuid4().hex[:8]
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
            actor = seed_user(db, "Round HTTP PM", "NONE", b"p" * 32)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,"
                       "department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                       (ids["project"], actor, ids["department"]))
            survey, version = definition.insert_valid(
                db, ids, name="Round HTTP survey")
            approve_definition(db, ids, survey, version)
            question = db.execute(
                "SELECT question_row_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,)).fetchone()[0]
            evidence, document, document_version, fingerprint = insert_evidence(db, ids)
            round_id, assignment, response, answer = (uuid.uuid4() for _ in range(4))
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.srv_questions SET required=false "
                           "WHERE survey_version_id=%s AND question_row_id<>%s",
                           (version, question))
                db.execute("INSERT INTO plm.srv_rounds(survey_round_id,survey_id,"
                           "survey_version_id,project_id,round_no,round_state,opened_by,"
                           "opened_at,created_by,updated_by,lock_version) VALUES "
                           "(%s,%s,%s,%s,1,'OPEN',%s,statement_timestamp(),%s,%s,1)",
                           (round_id, survey, version, ids["project"], actor, actor, actor))
                db.execute("INSERT INTO plm.srv_assignments(survey_assignment_id,"
                           "survey_round_id,survey_id,survey_version_id,project_id,"
                           "department_id,assignee_user_id,submission_state,submitted_by,"
                           "submitted_at,validated_by,validated_at,created_by,updated_by,"
                           "lock_version) VALUES (%s,%s,%s,%s,%s,%s,%s,'VALIDATED',%s,"
                           "statement_timestamp(),%s,statement_timestamp(),%s,%s,3)",
                           (assignment, round_id, survey, version, ids["project"],
                            ids["department"], actor, actor, actor, actor, actor))
                db.execute("INSERT INTO plm.srv_responses(survey_response_id,"
                           "survey_assignment_id,survey_round_id,survey_id,survey_version_id,"
                           "project_id,question_row_id,response_source,recorded_by,recorded_at) "
                           "VALUES (%s,%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,statement_timestamp())",
                           (response, assignment, round_id, survey, version,
                            ids["project"], question, actor))
                db.execute("INSERT INTO plm.srv_answers(survey_answer_id,survey_response_id,"
                           "survey_assignment_id,question_row_id,project_id,answer_value) "
                           "VALUES (%s,%s,%s,%s,%s,to_jsonb('answer'::text))",
                           (answer, response, assignment, question, ids["project"]))
                db.execute("INSERT INTO plm.srv_answer_evidence_refs(survey_answer_id,"
                           "survey_response_id,survey_assignment_id,question_row_id,project_id,"
                           "document_id,document_version_id,evidence_id,"
                           "observed_evidence_lock_version,content_fingerprint,recorded_by,"
                           "recorded_at,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,"
                           "statement_timestamp(),0)",
                           (answer, response, assignment, question, ids["project"], document,
                            document_version, evidence, fingerprint, actor))

        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex(), "record.pdf")
        runtime = create_database_runtime(url)
        guard = Guard(); guard.enabled = True
        routers = create_windows_survey_routers(
            runtime, sessions=Sessions(), origins=LoginOriginPolicy(["http://localhost"]),
            license_guard=guard, audit=AuditService(SqlAlchemyAuditRepository()),
            include_write=True, resolver=Keys(), documents=Documents(facts),
            downloads=Downloads(document_version, fingerprint), parse_results=object())
        app = create_app(survey_read_router=routers.reads,
                         survey_command_router=routers.commands)
        path = f"/api/v1/projects/{ids['project']}/survey-rounds/{round_id}"
        key = str(uuid.uuid4())
        with TestClient(app, base_url="http://localhost") as client:
            closed = client.post(path + ":close", headers=headers(key=key), content=b"")
            assert closed.status_code == 200, closed.text
            data = closed.json()["data"]
            assert data["state"] == "CLOSED" and len(data["close_report_fingerprint"]) == 64
            assert closed.headers["etag"] == '"v2"'
            replay = client.post(path + ":close", headers=headers(key=key), content=b"")
            assert replay.status_code == 200 and replay.json()["data"] == data
            detail = client.get(path, headers=headers())
            assert detail.status_code == 200 and detail.json()["data"]["state"] == "CLOSED"
            listing = client.get(
                f"/api/v1/projects/{ids['project']}/survey-rounds?page_size=1",
                headers=headers())
            assert listing.status_code == 200
            assert listing.json()["data"]["items"][0]["survey_round_id"] == str(round_id)
            refused = client.post(
                path + ":close", headers=headers(key=str(uuid.uuid4()), match='"v2"'),
                content=b"")
            assert refused.status_code == 422
        with connect(database) as db:
            row = db.execute("SELECT round_state,closed_by,lock_version,"
                             "octet_length(close_report_fingerprint) FROM plm.srv_rounds "
                             "WHERE survey_round_id=%s", (round_id,)).fetchone()
            assert row == ("CLOSED", actor, 2, 32), row
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action="
                              "'SURVEY_ROUND_CLOSED' AND target_object_id=%s",
                              (round_id,)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                              "operation='V1_SURVEY_ROUND_CLOSE' AND result_ref_id=%s",
                              (round_id,)).fetchone()[0] == 1
        command.check(cfg)
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print("SUR_02_A06_P01_ROUND_HTTP_CLOSE_PASS: seven Round routes composed; atomic completeness CLOSE, receipt replay, Audit, read projection, terminal refusal and drift verified on Windows 11/PostgreSQL 18")


if __name__ == "__main__": main()
