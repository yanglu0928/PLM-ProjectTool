"""Windows 11/PostgreSQL 18.6 HTTP proof for Survey definition composition."""

from __future__ import annotations

import runpy
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
    SURVEY_CURSOR_KEY_REF, SURVEY_VERSION_CURSOR_KEY_REF,
    create_windows_survey_routers,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"
))
validation = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a03-p03-version-validate" / "verify.py"
))
connect, seed_dependencies = schema["connect"], schema["seed_dependencies"]
seed_user, Guard, CSRF = validation["seed_user"], validation["Guard"], validation["CSRF"]
MANAGER_TOKEN, REVIEWER_TOKEN = b"m" * 32, b"r" * 32


class Keys:
    def resolve_key(self, key_ref: str) -> bytes | None:
        return {SURVEY_CURSOR_KEY_REF: b"s" * 32,
                SURVEY_VERSION_CURSOR_KEY_REF: b"v" * 32}.get(key_ref)


class Sessions:
    @staticmethod
    def validate(token, *, csrf_token=None, require_csrf=False):
        if token not in (MANAGER_TOKEN, REVIEWER_TOKEN):
            raise SessionError("AUTH_SESSION_EXPIRED")
        if require_csrf and csrf_token != CSRF:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def headers(token=MANAGER_TOKEN, *, key=None, etag=None, json=False):
    result = {"origin": "http://localhost",
              "cookie": "plm_session=" + token.hex(),
              "x-csrf-token": CSRF.hex()}
    if key is not None:
        result["idempotency-key"] = key
    if etag is not None:
        result["if-match"] = etag
    if json:
        result["content-type"] = "application/json"
    return result


def expect(response, status):
    if response.status_code != status:
        raise AssertionError((response.status_code, response.text))
    return response.json()["data"]


def question():
    return {"question_id": str(uuid.uuid4()), "topic": "Current process",
            "question_text": "How is approval performed?",
            "objective": "Confirm the approval path", "answer_type": "TEXT",
            "validation_rule": {"max_length": 1000}, "required": True,
            "condition_rule": None, "expected_output": "Confirmed workflow",
            "evidence_required": False, "options": [], "sources": [{
                "source_kind": "MANUAL", "handover_item_row_id": None,
                "handover_analysis_version_id": None,
                "handover_analysis_id": None,
                "capability_item_row_id": None,
                "capability_baseline_version_id": None,
                "capability_baseline_id": None,
                "template_document_version_id": None,
                "template_document_id": None,
                "manual_source_note": "Facilitated synthetic workshop",
            }]}


def main() -> None:
    database = "sur01a05a07_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin",
                         host="127.0.0.1", port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            manager = seed_user(db, "Survey HTTP Manager", "NONE", MANAGER_TOKEN)
            reviewer = seed_user(db, "Survey HTTP Reviewer", "NONE", REVIEWER_TOKEN)
            db.execute("""
                INSERT INTO plm.prj_project_members(
                  project_id,user_id,department_id,project_role)
                VALUES (%s,%s,%s,'PROJECT_MANAGER'),
                       (%s,%s,%s,'CUSTOMER_MANAGER')
            """, (ids["project"], manager, ids["department"],
                    ids["project"], reviewer, ids["department"]))

        runtime = create_database_runtime(url)
        try:
            guard, audit = Guard(), AuditService(SqlAlchemyAuditRepository())
            origins = LoginOriginPolicy(["http://localhost"])
            read_only = create_windows_survey_routers(
                runtime, sessions=Sessions(), origins=origins,
                license_guard=guard, audit=audit, include_write=False,
                resolver=Keys())
            assert read_only.commands is None and read_only.review_submission is None
            write = create_windows_survey_routers(
                runtime, sessions=Sessions(), origins=origins,
                license_guard=guard, audit=audit, include_write=True,
                resolver=Keys())
            review = create_windows_project_review_router(
                runtime, sessions=Sessions(), origins=origins,
                license_guard=guard, audit=audit)
            app = create_app(
                survey_read_router=write.reads,
                survey_command_router=write.commands,
                survey_review_submission_router=write.review_submission,
                review_command_router=review)
            root = f"/api/v1/projects/{ids['project']}/surveys"
            with TestClient(create_app(), base_url="http://localhost") as bare:
                assert bare.get(root).status_code == 404
                assert bare.post(root).status_code == 404
            with TestClient(create_app(survey_read_router=read_only.reads),
                            base_url="http://localhost") as readonly:
                assert readonly.get(root, headers=headers()).status_code == 200
                assert readonly.post(root, headers=headers()).status_code == 405

            with TestClient(app, base_url="http://localhost") as client:
                created = expect(client.post(
                    root, headers=headers(key=str(uuid.uuid4()), json=True),
                    json={"name": "Synthetic customer survey"}), 201)
                survey_id = created["survey_id"]
                survey_path = f"{root}/{survey_id}"
                patched = expect(client.patch(
                    survey_path, headers=headers(etag=created["etag"], json=True),
                    json={"name": "Synthetic current-state survey"}), 200)
                assert expect(client.get(root + "?page_size=1", headers=headers()), 200)["items"]
                assert expect(client.get(survey_path, headers=headers()), 200)["name"] == patched["name"]
                version = expect(client.post(
                    survey_path + "/versions",
                    headers=headers(key=str(uuid.uuid4()), etag=patched["etag"], json=True),
                    json={"questions": [question()],
                          "target_department_ids": [str(ids["department"])]}), 201)
                version_id = version["survey_version_id"]
                version_path = survey_path + f"/versions/{version_id}"
                assert expect(client.get(survey_path + "/versions?page_size=1",
                                         headers=headers()), 200)["items"]
                details = expect(client.get(version_path, headers=headers()), 200)
                assert details["questions"][0]["sources"][0]["source_kind"] == "MANUAL"
                report = expect(client.post(
                    version_path + ":validate",
                    headers=headers(key=str(uuid.uuid4()))), 200)
                assert report["valid"] is True
                submit_key = str(uuid.uuid4())
                body = {"reviewer_ids": [str(reviewer)],
                        "policy_ref": "SURVEY_ALL_V1",
                        "due_at": None, "submission_note": None}
                submitted = expect(client.post(
                    version_path + ":submit-review",
                    headers=headers(key=submit_key, json=True), json=body), 201)
                replayed = expect(client.post(
                    version_path + ":submit-review",
                    headers=headers(key=submit_key, json=True), json=body), 201)
                assert replayed["review_round_id"] == submitted["review_round_id"]
                decision_path = (f"/api/v1/projects/{ids['project']}/reviews/"
                    f"{submitted['review_id']}/rounds/{submitted['review_round_id']}:decide")
                approved = expect(client.post(
                    decision_path, headers=headers(REVIEWER_TOKEN, key=str(uuid.uuid4()), json=True),
                    json={"decision": "APPROVE", "comment": None}), 200)
                assert approved["state"] == "APPROVED"
                approved_version = expect(client.get(version_path, headers=headers()), 200)
                assert approved_version["state"] == "APPROVED"

                spare = expect(client.post(
                    root, headers=headers(key=str(uuid.uuid4()), json=True),
                    json={"name": "Archive candidate"}), 201)
                archived = expect(client.post(
                    f"{root}/{spare['survey_id']}:archive",
                    headers=headers(key=str(uuid.uuid4()), etag=spare["etag"])), 200)
                assert archived["state"] == "ARCHIVED"

            with connect(database) as db:
                assert db.execute("SELECT count(*) FROM plm.srv_surveys").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.srv_survey_versions").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.rvw_reviews WHERE subject_type='SRV-02'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.rvw_review_rounds WHERE round_state='APPROVED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s", (ids["project"],)).fetchone()[0] >= 5
            command.check(cfg)
            print("SUR_01_A05_A07_WINDOWS_COMPOSITION_PASS: ten frozen Survey definition operations, read-only/write composition, real PostgreSQL, HTTP, Review approval, replay and archive verified")
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
