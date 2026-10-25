"""Disposable Win11 ASGI/PG proof of Windows SectionVersion VALIDATE composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_section_version_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_create_owner_fixture",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def headers(token: bytes, csrf: bytes, key: str) -> dict[str, str]:
    return {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": key,
    }


def on_http(*, port, runtime, audit, license_guard, project, other_project,
            token, csrf, member_token, member_csrf, evidence,
            documents, downloads, parse_results, section, **_unused):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    args = dict(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads, parse_results=parse_results)
    try:
        create_windows_section_version_validate_router(
            **{**args, "documents": None})
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing Document proof dependency mounted VALIDATE")
    router = create_windows_section_version_validate_router(**args)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s AND version_no=1", (section,)).fetchone()[0]
    path = (f"/api/v1/projects/{project}/solution-sections/{section}"
            f"/versions/{version}:validate")
    with TestClient(create_app(), base_url="https://plm.example.test") as closed:
        assert closed.post(path, headers=headers(token, csrf, "validation-closed-0001")
                           ).status_code == 404
    with TestClient(create_app(
            solution_section_version_validate_router=router),
            base_url="https://plm.example.test") as app:
        first = app.post(path, headers=headers(token, csrf, "validation-first-0001"))
        assert first.status_code == 200, first.text
        data = first.json()["data"]
        assert data["facts"] == {
            "integrity": "PASS", "content": "PASS", "requirements": "PASS",
            "evidence": "PASS", "trace": "FAIL", "spec": "UNAVAILABLE"}
        assert data["valid"] and not data["ready_for_review"]
        replay = app.post(path, headers=headers(token, csrf, "validation-first-0001"))
        assert replay.status_code == 200 and replay.json()["data"] == data
        assert replay.json()["trace_id"] != first.json()["trace_id"]
        assert replay.headers["x-trace-id"] == replay.json()["trace_id"]
        assert app.post(path, headers=headers(token, csrf, "validation-body-0001"),
                        json={}).status_code == 400
        assert app.post(path.replace(str(project), str(other_project)),
                        headers=headers(token, csrf, "validation-other-0001")
                        ).status_code == 404
        assert app.post(path, headers=headers(token, b"x" * 32,
                                             "validation-csrf-0001")).status_code == 403
        wrong_origin = headers(token, csrf, "validation-origin-0001")
        wrong_origin["origin"] = "https://evil.test"
        assert app.post(path, headers=wrong_origin).status_code == 403
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.evd_evidence_records "
                       "SET eligibility_state='INELIGIBLE',lock_version=lock_version+1 "
                       "WHERE evidence_id=%s", (evidence,))
        drift = app.post(path, headers=headers(token, csrf, "validation-drift-0001"))
        assert drift.status_code == 200, drift.text
        assert drift.json()["data"]["facts"]["evidence"] == "UNAVAILABLE"
        assert not drift.json()["data"]["valid"]
        assert app.post(path, headers=headers(token, csrf, "validation-first-0001")
                        ).json()["data"] == data
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.evd_evidence_records "
                       "SET eligibility_state='ELIGIBLE',lock_version=lock_version+1 "
                       "WHERE evidence_id=%s", (evidence,))
        member = app.post(path, headers=headers(
            member_token, member_csrf, "validation-member-0001"))
        assert member.status_code == 200 and member.json()["data"]["valid"]
    denied = create_windows_section_version_validate_router(
        **{**args, "license_guard": prior._DeniedLicense()})
    with TestClient(create_app(
            solution_section_version_validate_router=denied),
            base_url="https://plm.example.test") as app:
        assert app.post(path, headers=headers(token, csrf, "validation-license-0001")
                        ).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                          "WHERE operation='V1_SOL_SECTION_VERSION_VALIDATE'").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_SECTION_VERSION_VALIDATED'").fetchone()[0] == 3
    print("SOL_05_A04_P05_VALIDATE_WINDOWS_HTTP_PG_PASS: explicit composition, "
          "real Session/PG/source, first/replay/drift/member/isolation/License")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_http))
