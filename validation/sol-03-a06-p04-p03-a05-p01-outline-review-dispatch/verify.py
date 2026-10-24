"""Full-source isolated PG18 Outline Review customer read and approval."""

from __future__ import annotations

import importlib.util
import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import uuid

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_read_router,
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_review_subject,
    create_windows_outline_review_submission_service,
    create_windows_outline_review_submission_router,
    create_windows_outline_version_create_router,
    create_windows_outline_version_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.solution.application.outline_submit_review import (
    OutlineReviewSubmissionError, SubmitOutlineReview,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_full_sources_for_review",
    ROOT / "validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py")
assert SPEC and SPEC.loader
full = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(full)


def _review_full(**context) -> None:
    outline, section, requirement, requirement_version = (
        full._approved_section_v2(**context))
    project, port = context["project"], context["port"]
    runtime, token, csrf, guard, audit = (context[name] for name in (
        "runtime", "token", "csrf", "license_guard", "audit"))
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(),
        audit=audit)
    with tempfile.TemporaryDirectory(prefix="plm-outline-review-pg-") as root:
        storage = Path(root)
        create_router = create_windows_outline_version_create_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit,
            document_storage_root=storage,
            parse_result_storage_root=storage)
        validate_router = create_windows_outline_version_validate_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit,
            document_storage_root=storage,
            parse_result_storage_root=storage,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"])
        path = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
        payload = {
            "section_ids": [str(section)],
            "requirement_refs": [{
                "requirement_id": str(requirement),
                "requirement_version_id": str(requirement_version),
            }],
            "reference_refs": [], "missing_declarations": [],
            "conflict_declarations": [],
        }
        with TestClient(create_app(
                solution_outline_version_create_router=create_router,
                solution_outline_version_validate_router=validate_router),
                base_url="https://plm.example.test") as app:
            created = app.post(path, headers=full._headers(
                token, csrf, "outline-review-pg-create-0001"), json=payload)
            assert created.status_code == 201, created.text
            version = uuid.UUID(
                created.json()["data"]["solution_outline_version_id"])
            validated = app.post(f"{path}/{version}:validate",
                                 headers=full._headers(
                                     token, csrf,
                                     "outline-review-pg-validate-0001"))
            assert validated.status_code == 200, validated.text
            assert validated.json()["data"]["facts"] == {
                "order": "PASS", "source": "PASS", "coverage": "PASS"}
        with psycopg.connect(**full._connection(port)) as db:
            reviewer = db.execute(
                "SELECT user_id FROM plm.prj_project_members WHERE "
                "project_id=%s AND project_role='CUSTOMER_MEMBER' "
                "AND state='ACTIVE' LIMIT 1", (project,)).fetchone()[0]
        service = create_windows_outline_review_submission_service(
            runtime=runtime, license_guard=guard, audit=audit,
            document_storage_root=storage,
            parse_result_storage_root=storage,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"])
        command = SubmitOutlineReview(
            token, csrf, uuid.uuid4(), project, outline, version,
            (reviewer,), "SOLUTION_OUTLINE_ALL_V1",
            "outline-review-pg-submit-0001")
        router = create_windows_outline_review_submission_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit,
            document_storage_root=storage,
            parse_result_storage_root=storage,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"])
        submit_path = f"{path}/{version}:submit-review"
        submit_body = {
            "reviewer_ids": [str(reviewer)],
            "policy_ref": "SOLUTION_OUTLINE_ALL_V1",
            "due_at": None, "submission_note": None,
        }
        headers = full._headers(token, csrf, "outline-review-pg-submit-0001")
        with TestClient(create_app(
                solution_outline_review_submission_router=router),
                base_url="https://plm.example.test") as app:
            first = app.post(submit_path, headers=headers, json=submit_body)
            assert first.status_code == 201, first.text
            assert first.headers["etag"] == '"v1"'
            assert first.headers["cache-control"] == "no-store"
            data = first.json()["data"]
            assert data["subject_type"] == "SOL-03"
            assert data["solution_outline_id"] == str(outline)
            assert data["solution_outline_version_id"] == str(version)
            replay = app.post(submit_path, headers=headers, json=submit_body)
            assert replay.status_code == 201 and replay.json()["data"] == data
            assert app.post(submit_path, headers={**headers,
                "origin": "https://untrusted.test"},
                json=submit_body).status_code == 403
            assert app.post(submit_path, headers=headers,
                json={**submit_body, "extra": True}).status_code == 400
            assert app.post(submit_path.replace(str(project), str(uuid.uuid4())),
                headers={**headers, "idempotency-key": "outline-review-pg-wrong-project-0002"},
                json=submit_body).status_code == 404
            assert app.post(submit_path.replace(str(version), str(uuid.uuid4())),
                headers={**headers, "idempotency-key": "outline-review-pg-wrong-version-0002"},
                json=submit_body).status_code in (404, 409, 422)
            second = app.post(submit_path, headers={**headers,
                "idempotency-key": "outline-review-pg-second-key-0002"},
                json=submit_body)
            assert second.status_code == 404, (
                second.status_code, second.text)
        submitted = SimpleNamespace(
            review_id=uuid.UUID(data["review_id"]),
            round_id=uuid.UUID(data["review_round_id"]))
        assert service.submit(command).review_id == submitted.review_id
        with psycopg.connect(**full._connection(port)) as db:
            assert db.execute(
                "SELECT version_state,review_ref,review_round_ref FROM "
                "plm.sol_outline_versions WHERE solution_outline_version_id=%s",
                (version,)).fetchone() == (
                    "IN_REVIEW", submitted.review_id, submitted.round_id)
            assert db.execute(
                "SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s "
                "AND subject_type='SOL-03' AND subject_id=%s",
                (submitted.review_id, outline)).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.rvw_subject_snapshots WHERE "
                "review_id=%s AND review_round_id=%s AND "
                "subject_version_id=%s",
                (submitted.review_id, submitted.round_id, version)
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.sol_outline_review_state_results "
                "WHERE solution_outline_version_id=%s AND event_type='START'",
                (version,)).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_SOL_OUTLINE_VERSION_SUBMIT_REVIEW' "
                "AND result_ref_id=%s", (submitted.round_id,)
            ).fetchone()[0] == 1
        for invalid in (
                replace(command, project_id=uuid.uuid4(),
                        idempotency_key="outline-review-pg-wrong-project-0001"),
                replace(command, outline_version_id=uuid.uuid4(),
                        idempotency_key="outline-review-pg-wrong-version-0001"),
                replace(command, idempotency_key="outline-review-pg-new-key-0001")):
            try:
                service.submit(invalid)
            except OutlineReviewSubmissionError:
                pass
            else:
                raise AssertionError("invalid or second Outline submit accepted")
        with psycopg.connect(**full._connection(port)) as db:
            section_version = db.execute(
                "SELECT current_approved_version_ref FROM plm.sol_sections "
                "WHERE solution_section_id=%s", (section,)).fetchone()[0]
            edge = db.execute(
                "SELECT trace_link_id FROM plm.trc_links WHERE project_id=%s "
                "AND target_object_id=%s AND target_version_id=%s "
                "AND link_state='ACTIVE' AND relation_type='IMPLEMENTS'",
                (project, section, section_version)).fetchone()[0]
        terminal_owner = create_windows_outline_review_subject(
            runtime=runtime, license_guard=guard, audit=audit,
            document_storage_root=storage,
            parse_result_storage_root=storage,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"],
            terminal_context=True)
        customer_token = uuid.uuid4().bytes * 2
        customer_csrf = uuid.uuid4().bytes * 2
        with psycopg.connect(**full._connection(port)) as db:
            db.execute(
                "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,"
                "user_id,credential_version,idle_expires_at,absolute_expires_at) "
                "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
                "statement_timestamp()+interval '1 hour')",
                (hashlib.sha256(customer_token).digest(),
                 hashlib.sha256(customer_csrf).digest(), reviewer))
        read_router = create_windows_project_review_read_router(
            runtime, origins=origins, license_guard=guard, audit=audit,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"],
            outline_subject=terminal_owner)
        review_router = create_windows_project_review_router(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, documents=context["documents"],
            downloads=context["downloads"],
            parse_results=context["parse_results"],
            outline_subject=terminal_owner)
        review_path = f"/api/v1/projects/{project}/reviews/{submitted.review_id}"
        decide_path = (f"{review_path}/rounds/{submitted.round_id}:decide")
        customer_headers = full._headers(
            customer_token, customer_csrf, "outline-review-pg-approve-0001")
        with TestClient(create_app(
                review_read_router=read_router,
                review_command_router=review_router),
                base_url="https://plm.example.test") as app:
            before = app.get(review_path, headers=customer_headers)
            assert before.status_code == 200, before.text
            assert before.json()["data"]["subject_ref"] == {
                "resource_type": "SOL-03", "resource_id": str(outline)}
            assert app.get(review_path.replace(str(project), str(uuid.uuid4())),
                           headers=customer_headers).status_code == 404
            creator, revoker = full.terminal.prior._trace_services(
                runtime=runtime, license_guard=guard, audit=audit)
            revoker.revoke(full.terminal.prior.RevokeTraceLink(
                token, csrf, uuid.uuid4(), project, edge, 0),
                idempotency_key="outline-review-pg-revoke-0001")
            denied = app.post(decide_path, headers={
                **customer_headers,
                "idempotency-key": "outline-review-pg-denied-0001"},
                json={"decision": "APPROVE", "comment": None})
            assert denied.status_code == 404, denied.text
            with psycopg.connect(**full._connection(port)) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.rvw_review_decisions "
                    "WHERE review_round_id=%s",
                    (submitted.round_id,)).fetchone()[0] == 0
            creator.create_refs(full.terminal.prior.CreateTraceLinkRefs(
                token, csrf, uuid.uuid4(), project,
                full.terminal.prior.TraceResourceVersionRef(
                    "REQ-03", requirement, requirement_version),
                full.terminal.prior.TraceResourceVersionRef(
                    "SOL-05", section, section_version),
                "IMPLEMENTS"),
                idempotency_key="outline-review-pg-restore-0001")
            approved = app.post(decide_path, headers=customer_headers,
                                json={"decision": "APPROVE", "comment": None})
            assert approved.status_code == 200, approved.text
            replay = app.post(decide_path, headers=customer_headers,
                              json={"decision": "APPROVE", "comment": None})
            assert replay.status_code == 200
            assert replay.json()["data"] == approved.json()["data"]
            after = app.get(review_path, headers=customer_headers)
            assert after.status_code == 200 and after.json()["data"]["state"] == "APPROVED"
        with psycopg.connect(**full._connection(port)) as db:
            assert db.execute(
                "SELECT v.version_state,o.current_approved_version_ref FROM "
                "plm.sol_outline_versions v JOIN plm.sol_outlines o ON "
                "o.solution_outline_id=v.solution_outline_id WHERE "
                "v.solution_outline_version_id=%s", (version,)
            ).fetchone() == ("APPROVED", version)
            assert db.execute(
                "SELECT count(*) FROM plm.sol_outline_review_state_results "
                "WHERE solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.rvw_review_decisions WHERE "
                "review_round_id=%s", (submitted.round_id,)
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE "
                "action='SOLUTION_OUTLINE_VERSION_APPROVED' AND "
                "target_version_id=%s", (version,)
            ).fetchone()[0] == 1
    print("SOL_03_A06_P04_P03_A05_P01_OUTLINE_REVIEW_DISPATCH_PG_PASS")


if __name__ == "__main__":
    def hooked(case: str, **context):
        assert case == "APPROVE"
        full.original_terminal(case, **context)
        _review_full(**context)

    full.terminal._terminal = hooked
    full.terminal._run("APPROVE")
