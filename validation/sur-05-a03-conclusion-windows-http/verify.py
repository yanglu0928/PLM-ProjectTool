"""Windows 11/PostgreSQL 18 proof for SurveyConclusion HTTP composition."""

from __future__ import annotations

import runpy
import io
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_router,
)
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
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.application.prepare_download import (
    VerifiedDownload,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"
))
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, definition = schema["connect"], schema["load_definition_fixture"]()
approve_definition = schema["approve_definition"]
insert_evidence = schema["insert_evidence"]
seed_user, Guard, CSRF = auth["seed_user"], auth["Guard"], auth["CSRF"]
MANAGER_TOKEN, REVIEWER_TOKEN = b"m" * 32, b"r" * 32


class Keys:
    def resolve_key(self, key_ref):
        return {
            SURVEY_CURSOR_KEY_REF: b"s" * 32,
            SURVEY_VERSION_CURSOR_KEY_REF: b"v" * 32,
        }.get(key_ref)


class Sessions:
    @staticmethod
    def validate(token, *, csrf_token=None, require_csrf=False):
        if token not in (MANAGER_TOKEN, REVIEWER_TOKEN):
            raise SessionError("AUTH_SESSION_EXPIRED")
        if require_csrf and csrf_token != CSRF:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Documents:
    def __init__(self, facts):
        self.facts = facts

    def get_source_facts_for_evidence(
        self, transaction, query, document_id, document_version_id,
    ):
        return self.facts


class Downloads:
    def __init__(self, document_version_id, content_sha256):
        self.document_version_id = document_version_id
        self.content_sha256 = content_sha256

    def prepare_in_transaction(
        self, transaction, query, document_id, document_version_id,
    ):
        return VerifiedDownload(
            self.document_version_id, 0, "application/octet-stream",
            self.content_sha256, io.BytesIO(b""),
        )


def headers(token=MANAGER_TOKEN, *, key=None, match=None):
    result = {
        "origin": "http://localhost",
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": CSRF.hex(),
    }
    if key is not None:
        result["idempotency-key"] = key
    if match is not None:
        result["if-match"] = match
    return result


def expect(response, status):
    if response.status_code != status:
        raise AssertionError((response.status_code, response.text))
    return response.json()["data"]


def main() -> None:
    database = "sur05a03_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin",
            host="127.0.0.1", port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            manager = seed_user(db, "Conclusion HTTP PM", "NONE", MANAGER_TOKEN)
            reviewer = seed_user(
                db, "Conclusion HTTP Reviewer", "NONE", REVIEWER_TOKEN,
            )
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,"
                "department_id,project_role) VALUES "
                "(%s,%s,%s,'PROJECT_MANAGER'),"
                "(%s,%s,%s,'CUSTOMER_MANAGER')",
                (ids["project"], manager, ids["department"],
                 ids["project"], reviewer, ids["department"]),
            )
            survey, version = definition.insert_valid(
                db, ids, name="Conclusion HTTP survey",
            )
            approve_definition(db, ids, survey, version)
            questions = db.execute(
                "SELECT question_id,answer_type FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no", (version,),
            ).fetchall()
            evidence, document, document_version, evidence_fingerprint = (
                insert_evidence(db, ids)
            )
            round_id = uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.srv_rounds(survey_round_id,survey_id,"
                    "survey_version_id,project_id,round_no,round_state,opened_by,"
                    "opened_at,created_by,updated_by,lock_version) VALUES "
                    "(%s,%s,%s,%s,1,'OPEN',%s,statement_timestamp(),%s,%s,1)",
                    (round_id, survey, version, ids["project"], manager,
                     manager, manager),
                )

        runtime = create_database_runtime(url)
        guard, audit = Guard(), AuditService(SqlAlchemyAuditRepository())
        guard.enabled = True
        origins, opaque = LoginOriginPolicy(["http://localhost"]), object()
        documents = Documents(DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", evidence_fingerprint.hex(),
        ))
        downloads = Downloads(document_version, evidence_fingerprint)
        read_only = create_windows_survey_routers(
            runtime, sessions=Sessions(), origins=origins,
            license_guard=guard, audit=audit, include_write=False,
            resolver=Keys(),
        )
        routers = create_windows_survey_routers(
            runtime, sessions=Sessions(), origins=origins,
            license_guard=guard, audit=audit, include_write=True,
            resolver=Keys(), documents=documents, downloads=downloads,
            parse_results=opaque,
        )
        review = create_windows_project_review_router(
            runtime, sessions=Sessions(), origins=origins,
            license_guard=guard, audit=audit, documents=documents,
            downloads=downloads, parse_results=opaque,
        )
        app = create_app(
            survey_read_router=routers.reads,
            survey_command_router=routers.commands,
            survey_review_submission_router=routers.review_submission,
            review_command_router=review,
        )
        conclusion_root = f"/api/v1/projects/{ids['project']}/survey-conclusions"
        with TestClient(create_app(), base_url="http://localhost") as bare:
            assert bare.get(conclusion_root).status_code == 404
            assert bare.post(conclusion_root).status_code == 404
        with TestClient(
            create_app(survey_read_router=read_only.reads),
            base_url="http://localhost",
        ) as readonly:
            assert readonly.get(conclusion_root, headers=headers()).status_code == 200
            assert readonly.post(conclusion_root, headers=headers()).status_code == 405

        assignment_root = (
            f"/api/v1/projects/{ids['project']}/survey-rounds/{round_id}/assignments"
        )
        with TestClient(app, base_url="http://localhost") as client:
            assignment = expect(client.post(
                assignment_root, headers=headers(key=str(uuid.uuid4())),
                json={"department_id": str(ids["department"]),
                      "assignee_user_id": str(manager)},
            ), 201)
            assignment_id = assignment["survey_assignment_id"]
            assignment_path = f"{assignment_root}/{assignment_id}"
            etag = '"v0"'
            response_ids = []
            for question_id, answer_type in questions:
                answer = "YES" if answer_type == "SINGLE_CHOICE" else "answer"
                recorded = client.post(
                    assignment_path + "/responses",
                    headers=headers(key=str(uuid.uuid4()), match=etag),
                    json={
                        "question_id": str(question_id),
                        "response_source": "SELF_SERVICE",
                        "raw_answer": answer, "answer_value": answer,
                        "evidence_ids": [], "project_record_evidence_id": None,
                        "correction_of_response_id": None,
                    },
                )
                expect(recorded, 201)
                etag = recorded.headers["etag"]
                response_ids.append(recorded.json()["data"]["survey_response_id"])
            submitted = client.post(
                assignment_path + ":submit",
                headers=headers(key=str(uuid.uuid4()), match=etag), content=b"",
            )
            expect(submitted, 200)
            validated = client.post(
                assignment_path + ":validate",
                headers=headers(
                    key=str(uuid.uuid4()), match=submitted.headers["etag"],
                ),
                content=b"",
            )
            assert expect(validated, 200)["state"] == "VALIDATED"

            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                    "WHERE survey_round_id=%s",
                    (manager, b"c" * 32, manager, round_id),
                )

            body = {
                "survey_id": str(survey), "round_refs": [str(round_id)],
                "department_conclusions": [{
                    "department_id": str(ids["department"]),
                    "title": "Confirmed scope",
                    "statement": "Customer confirmed the current process.",
                    "response_refs": [response_ids[0]],
                }],
                "module_conclusions": [], "evidence_refs": [{
                    "evidence_id": str(evidence), "reference_role": "SUPPORT",
                }],
                "open_issue_refs": [], "ai_task_refs": [],
                "supersedes_ref": None,
            }
            created = client.post(
                conclusion_root, headers=headers(key=str(uuid.uuid4())), json=body,
            )
            created_data = expect(created, 201)
            conclusion_id = created_data["survey_conclusion_id"]
            conclusion_path = f"{conclusion_root}/{conclusion_id}"
            assert expect(client.get(conclusion_root + "?page_size=20",
                                     headers=headers()), 200)["items"]
            detail = expect(client.get(conclusion_path, headers=headers()), 200)
            assert detail["department_conclusions"][0]["response_refs"] == [
                response_ids[0]
            ]
            checked = expect(client.post(
                conclusion_path + ":validate",
                headers=headers(key=str(uuid.uuid4())), content=b"",
            ), 200)
            assert checked["valid"] is True, checked
            review_submission = expect(client.post(
                conclusion_path + ":submit-review",
                headers=headers(key=str(uuid.uuid4())),
                json={
                    "reviewer_ids": [str(reviewer)],
                    "policy_ref": "SURVEY_CONCLUSION_ALL_V1",
                    "due_at": None, "submission_note": None,
                },
            ), 201)
            decision_path = (
                f"/api/v1/projects/{ids['project']}/reviews/"
                f"{review_submission['review_id']}/rounds/"
                f"{review_submission['review_round_id']}:decide"
            )
            approved = expect(client.post(
                decision_path,
                headers=headers(REVIEWER_TOKEN, key=str(uuid.uuid4())),
                json={"decision": "APPROVE", "comment": None},
            ), 200)
            assert approved["state"] == "APPROVED"
            assert expect(client.get(conclusion_path, headers=headers()), 200)[
                "state"
            ] == "APPROVED"

        with connect(database) as db:
            assert db.execute(
                "SELECT conclusion_state FROM plm.srv_conclusions WHERE "
                "survey_conclusion_id=%s", (conclusion_id,),
            ).fetchone()[0] == "APPROVED"
            assert db.execute(
                "SELECT count(*) FROM plm.rvw_reviews r JOIN plm.rvw_review_rounds rr "
                "ON rr.review_id=r.review_id WHERE r.subject_type='SRV-05' "
                "AND rr.subject_version_id=%s",
                (conclusion_id,),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action IN "
                "('SURVEY_CONCLUSION_CREATED','SURVEY_CONCLUSION_VALIDATED',"
                "'SURVEY_CONCLUSION_APPROVED') AND target_project_id=%s",
                (ids["project"],),
            ).fetchone()[0] == 3
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database),
            ))
    print(
        "SUR_05_A03_CONCLUSION_WINDOWS_HTTP_PASS: default/read-only/write "
        "composition, real five-operation FastAPI/PostgreSQL 18 chain and "
        "SRV-05 generic Review approval verified on Windows 11"
    )


if __name__ == "__main__":
    main()
