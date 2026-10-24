"""Disposable Win11/PG18 Outline current three-dimension integration proof."""

from __future__ import annotations

import importlib.util
import tempfile
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_version_create_router,
    create_windows_outline_version_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "section_terminal_for_outline_validation",
    ROOT / "validation/sol-05-a04-p13-p06-p01-section-terminal-windows/verify.py",
)
assert spec is not None and spec.loader is not None
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)
original_terminal = terminal._terminal


def _headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def _after_approval(**context) -> None:
    original_terminal("APPROVE", **context)
    project, port = context["project"], context["port"]
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        row = db.execute(
            "SELECT s.solution_outline_id,s.solution_section_id,"
            "v.solution_section_version_id,r.requirement_id,"
            "r.requirement_version_id FROM plm.sol_sections s "
            "JOIN plm.sol_section_versions v ON "
            "v.solution_section_id=s.solution_section_id "
            "JOIN plm.sol_section_requirement_refs r ON "
            "r.solution_section_version_id=v.solution_section_version_id "
            "WHERE s.project_id=%s AND v.version_state='APPROVED' "
            "AND s.current_approved_version_ref=v.solution_section_version_id "
            "LIMIT 1", (project,),
        ).fetchone()
    assert row is not None, "approved Section fixture missing"
    outline, section, section_version, requirement, requirement_version = row
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        requirement_state = db.execute(
            "SELECT r.requirement_state,r.current_approved_version_ref,"
            "v.version_state,v.review_ref,v.review_round_ref "
            "FROM plm.req_requirements r JOIN plm.req_requirement_versions v "
            "ON v.requirement_id=r.requirement_id "
            "WHERE v.requirement_version_id=%s", (requirement_version,),
        ).fetchone()
    assert requirement_state[0] == "ACTIVE"
    assert requirement_state[1] == requirement_version
    assert requirement_state[2] == "APPROVED"
    runtime, token, csrf = (context[name] for name in (
        "runtime", "token", "csrf"))
    audit, license_guard = context["audit"], context["license_guard"]
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(),
        audit=audit,
    )
    storage = tempfile.TemporaryDirectory(prefix="plm-outline-real-pg-")
    storage_root = Path(storage.name)
    create_router = create_windows_outline_version_create_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        document_storage_root=storage_root,
        parse_result_storage_root=storage_root,
    )
    validate_router = create_windows_outline_version_validate_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        document_storage_root=storage_root,
        parse_result_storage_root=storage_root,
        documents=context["documents"], downloads=context["downloads"],
        parse_results=context["parse_results"],
    )
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
        solution_outline_version_validate_router=validate_router,
    ), base_url="https://plm.example.test") as app:
        created = app.post(path, headers=_headers(
            token, csrf, "outline-real-pg-create-0001"), json=payload)
        assert created.status_code == 201, created.text
        version = uuid.UUID(created.json()["data"]["solution_outline_version_id"])
        validate_path = f"{path}/{version}:validate"
        first = app.post(validate_path, headers=_headers(
            token, csrf, "outline-real-pg-validate-0001"))
        assert first.status_code == 200, first.text
        facts = first.json()["data"]["facts"]
        assert facts == {
            "order": "PASS", "source": "PASS", "coverage": "UNAVAILABLE"}, facts
        replay = app.post(validate_path, headers=_headers(
            token, csrf, "outline-real-pg-validate-0001"))
        assert replay.status_code == 200 and replay.json()["data"] == first.json()["data"]
        fresh = app.post(validate_path, headers=_headers(
            token, csrf, "outline-real-pg-validate-0002"))
        assert fresh.status_code == 200 and fresh.json()["data"]["facts"] == facts
        assert not first.json()["data"]["ready_for_review"]
        assert not fresh.json()["data"]["ready_for_review"]
        wrong_project = app.post(
            validate_path.replace(str(project), str(uuid.uuid4())),
            headers=_headers(token, csrf, "outline-real-pg-cross-0001"))
        assert wrong_project.status_code == 404
        bad_csrf = app.post(validate_path, headers=_headers(
            token, b"x" * 32, "outline-real-pg-csrf-0001"))
        assert bad_csrf.status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='SOL_OUTLINE_VERSION_VALIDATED' AND target_version_id=%s",
            (version,),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_OUTLINE_VERSION_VALIDATE'",
        ).fetchone()[0] == 2
    print("SOL_03_A06_P03_A05_P03_A05_INCOMPLETE_REQUIREMENT_FAIL_CLOSED_PASS")
    storage.cleanup()


if __name__ == "__main__":
    def hooked(case: str, **context):
        assert case == "APPROVE"
        _after_approval(**context)
    terminal._terminal = hooked
    terminal._run("APPROVE")
