"""Disposable Win11/PG18 synthetic customer Section terminal Review proof."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import uuid

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_solution_outline import (
    _windows_section_current_validator,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.section_version_validation_contract import SectionCurrentFactQuery
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_submit_for_terminal",
    ROOT / "validation/sol-05-a04-p13-p05-p03-section-review-submit-windows/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _terminal(case: str, **context):
    assert case in ("APPROVE", "RETURN", "WITHDRAW")
    prior._after_submit(**context)
    project, port = context["project"], context["port"]
    connection = dict(host="127.0.0.1", port=port,
                      user="poc_admin", dbname="postgres")
    with psycopg.connect(**connection) as db:
        section, version, review_id, round_id = db.execute(
            "SELECT solution_section_id,solution_section_version_id,"
            "review_ref,review_round_ref FROM plm.sol_section_versions "
            "WHERE project_id=%s AND version_state='IN_REVIEW' "
            "ORDER BY version_no DESC LIMIT 1", (project,)).fetchone()
        reviewer = db.execute(
            "SELECT reviewer_id FROM plm.rvw_review_assignments "
            "WHERE review_round_id=%s", (round_id,)).fetchone()[0]
        requirement, requirement_version = db.execute(
            "SELECT requirement_id,requirement_version_id FROM "
            "plm.sol_section_requirement_refs WHERE "
            "solution_section_version_id=%s", (version,)).fetchone()
        edge = db.execute(
            "SELECT trace_link_id FROM plm.trc_links WHERE project_id=%s "
            "AND target_object_id=%s AND target_version_id=%s "
            "AND link_state='ACTIVE' AND relation_type='IMPLEMENTS'",
            (project, section, version)).fetchone()[0]
        token, csrf = uuid.uuid4().bytes + uuid.uuid4().bytes, uuid.uuid4().bytes + uuid.uuid4().bytes
        with db.transaction():
            db.execute(
                "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,"
                "user_id,credential_version,idle_expires_at,absolute_expires_at) "
                "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
                "statement_timestamp()+interval '1 hour')",
                (hashlib.sha256(token).digest(),
                 hashlib.sha256(csrf).digest(), reviewer))
    sessions = SessionService(
        unit_of_work=context["runtime"].unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=context["audit"])
    router = create_windows_project_review_router(
        runtime=context["runtime"], sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=context["license_guard"], audit=context["audit"],
        documents=context["documents"], downloads=context["downloads"],
        parse_results=context["parse_results"])
    authorization = ProjectAuthorizationService(
        unit_of_work=context["runtime"].unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    current = _windows_section_current_validator(
        runtime=context["runtime"], license_guard=context["license_guard"],
        authorization=authorization, documents=context["documents"],
        downloads=context["downloads"], parse_results=context["parse_results"],
        evidence_roles=ALL_MEMBERS)
    with context["runtime"].unit_of_work() as tx:
        version_view = SqlAlchemySectionVersionReadRepository().get(
            tx, project_id=project, section_id=section, version_id=version)
        facts = current.facts(tx, command=SectionCurrentFactQuery(
            token, uuid.uuid4(), project, section, version), version=version_view)
        assert all(getattr(facts, name) == "PASS" for name in (
            "integrity", "content", "requirements", "evidence", "trace", "spec")), facts
    path = (f"/api/v1/projects/{project}/reviews/{review_id}/rounds/"
            f"{round_id}:{'withdraw' if case == 'WITHDRAW' else 'decide'}")
    body = ({"reason": "Synthetic manager withdrawal"}
            if case == "WITHDRAW" else {"decision": case,
            "comment": None if case == "APPROVE" else "Synthetic return reason"})
    actor_token = context["token"] if case == "WITHDRAW" else token
    actor_csrf = context["csrf"] if case == "WITHDRAW" else csrf
    headers = {"cookie": "plm_session=" + actor_token.hex(),
               "origin": "https://plm.example.test",
               "x-csrf-token": actor_csrf.hex(),
               "idempotency-key": f"section-terminal-{case.lower()}-0001"}
    if case == "WITHDRAW":
        headers["if-match"] = '"v1"'
    with TestClient(create_app(review_command_router=router),
                    base_url="https://plm.example.test") as app:
        if case == "APPROVE":
            creator, revoker = prior._trace_services(
                runtime=context["runtime"],
                license_guard=context["license_guard"],
                audit=context["audit"])
            revoker.revoke(prior.RevokeTraceLink(
                context["token"], context["csrf"], uuid.uuid4(), project,
                edge, 0), idempotency_key="terminal-review-revoke-0001")
            denied = app.post(path, headers={
                **headers, "idempotency-key": "terminal-review-denied-0001"},
                json=body)
            assert denied.status_code == 404, denied.text
            with psycopg.connect(**connection) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.rvw_review_decisions "
                    "WHERE review_round_id=%s", (round_id,)).fetchone()[0] == 0
            creator.create_refs(prior.CreateTraceLinkRefs(
                context["token"], context["csrf"], uuid.uuid4(), project,
                prior.TraceResourceVersionRef(
                    "REQ-03", requirement, requirement_version),
                prior.TraceResourceVersionRef("SOL-05", section, version),
                "IMPLEMENTS"), idempotency_key="terminal-review-restore-0001")
        first = app.post(path, headers=headers, json=body)
        assert first.status_code == 200, first.text
        replay = app.post(path, headers=headers, json=body)
        assert replay.status_code == 200, replay.text
        assert first.json()["data"] == replay.json()["data"]
    state = "APPROVED" if case == "APPROVE" else "RETURNED"
    with psycopg.connect(**connection) as db:
        version_state, current = db.execute(
            "SELECT v.version_state,s.current_approved_version_ref "
            "FROM plm.sol_section_versions v JOIN plm.sol_sections s "
            "ON s.solution_section_id=v.solution_section_id "
            "WHERE v.solution_section_version_id=%s", (version,)).fetchone()
        assert version_state == state
        assert current == (version if case == "APPROVE" else None)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_section_review_state_results "
            "WHERE solution_section_version_id=%s AND event_type=%s",
            (version, "WITHDRAWN" if case == "WITHDRAW" else state)).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions "
            "WHERE review_round_id=%s", (round_id,)).fetchone()[0] == (
                0 if case == "WITHDRAW" else 1)
    print(f"SOL_05_A04_P13_P06_P01_SECTION_TERMINAL_{case}_WINDOWS_PASS")


def _run(case: str):
    fixture = prior.prior.fixture
    fixture._after_submit = lambda **context: _terminal(case, **context)
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))


if __name__ == "__main__":
    _run("APPROVE")
    _run("RETURN")
    _run("WITHDRAW")
