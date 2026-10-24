"""Full-source isolated PG18 Outline Review START through the real service graph."""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path
import tempfile
import uuid

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_review_subject,
    create_windows_outline_review_submission_service,
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
from plm_assistant.modules.solution.application.outline_review_readiness import (
    OutlineReviewReadinessError,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery,
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
        submitted = service.submit(command)
        assert submitted.subject_type == "SOL-03"
        assert submitted.subject_version_id == version
        assert service.submit(command) == submitted
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
        _, revoker = full.terminal.prior._trace_services(
            runtime=runtime, license_guard=guard, audit=audit)
        revoker.revoke(full.terminal.prior.RevokeTraceLink(
            token, csrf, uuid.uuid4(), project, edge, 0),
            idempotency_key="outline-review-pg-revoke-0001")
        terminal_owner = create_windows_outline_review_subject(
            runtime=runtime, license_guard=guard, audit=audit,
            document_storage_root=storage,
            parse_result_storage_root=storage,
            documents=context["documents"], downloads=context["downloads"],
            parse_results=context["parse_results"],
            terminal_context=True)
        with runtime.unit_of_work() as tx:
            try:
                terminal_owner._readiness.prove(
                    tx, query=OutlineCurrentFactQuery(
                        token, uuid.uuid4(), project, outline, version),
                    required_state="IN_REVIEW")
            except OutlineReviewReadinessError:
                pass
            else:
                raise AssertionError("revoked Trace accepted by terminal proof")
        with psycopg.connect(**full._connection(port)) as db:
            assert db.execute(
                "SELECT version_state FROM plm.sol_outline_versions WHERE "
                "solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == "IN_REVIEW"
            assert db.execute(
                "SELECT count(*) FROM plm.sol_outline_review_state_results "
                "WHERE solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == 1
    print("SOL_03_A06_P04_P03_A03_P02_OUTLINE_REVIEW_PG_PASS")


if __name__ == "__main__":
    def hooked(case: str, **context):
        assert case == "APPROVE"
        full.original_terminal(case, **context)
        _review_full(**context)

    full.terminal._terminal = hooked
    full.terminal._run("APPROVE")
