"""Disposable Win11 HTTP/PG Section VALIDATE after Trace create/revoke."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_version_validate_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.trace.application.revoke_link import (
    RevokeTraceLink, TraceRevokeService,
)
from plm_assistant.modules.trace.infrastructure.revoke_repository import (
    SqlAlchemyTraceRevokeRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prior = module(
    "section_trace_windows_previous",
    "validation/sol-05-a04-p05-section-version-validate-windows/verify.py")
trace_fixture = module(
    "section_trace_windows_coverage",
    "validation/trc-01-a03-p03-implements-coverage/verify.py")


def on_http(*, port, runtime, audit, license_guard, project, other_project,
            token, csrf, section, requirement, requirement_version,
            documents, downloads, parse_results, **kwargs):
    inputs = dict(
        port=port, runtime=runtime, audit=audit,
        license_guard=license_guard, project=project,
        other_project=other_project, token=token, csrf=csrf,
        section=section, requirement=requirement,
        requirement_version=requirement_version,
        documents=documents, downloads=downloads,
        parse_results=parse_results, **kwargs)
    prior.on_http(**inputs)  # No link: current Trace FAIL, old-key replay stable.
    trace_fixture.on_coverage(**inputs)  # Create/revoke/recreate one exact edge.
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_section_version_validate_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s AND version_no=1", (section,)).fetchone()[0]
        link = db.execute(
            "SELECT trace_link_id FROM plm.trc_links WHERE "
            "target_version_id=%s AND link_state='ACTIVE'", (version,)).fetchone()[0]
    path = (f"/api/v1/projects/{project}/solution-sections/{section}"
            f"/versions/{version}:validate")
    with TestClient(create_app(
            solution_section_version_validate_router=router),
            base_url="https://plm.example.test") as app:
        present = app.post(path, headers=prior.headers(
            token, csrf, "section-trace-present-0001"))
        assert present.status_code == 200, present.text
        data = present.json()["data"]
        assert data["facts"] == {
            "integrity": "PASS", "content": "PASS", "requirements": "PASS",
            "evidence": "PASS", "trace": "PASS", "spec": "UNAVAILABLE"}, data
        assert data["valid"] and not data["ready_for_review"]
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        revoker = TraceRevokeService(
            unit_of_work=runtime.unit_of_work,
            sessions=SqlAlchemyProjectWriteAccess(), projects=authorization,
            license_guard=license_guard,
            repository=SqlAlchemyTraceRevokeRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
        revoker.revoke(RevokeTraceLink(
            token, csrf, uuid.uuid4(), project, link, 0),
            idempotency_key="section-trace-final-revoke-0001")
        missing = app.post(path, headers=prior.headers(
            token, csrf, "section-trace-revoked-0001"))
        assert missing.status_code == 200, missing.text
        assert missing.json()["data"]["facts"]["trace"] == "FAIL"
        assert not missing.json()["data"]["ready_for_review"]
        replay = app.post(path, headers=prior.headers(
            token, csrf, "section-trace-present-0001"))
        assert replay.status_code == 200
        assert replay.json()["data"] == data
    print("SOL_05_A04_P10_P02_SECTION_TRACE_WINDOWS_PG_PASS: "
          "no edge FAIL, ACTIVE PASS, revoked FAIL, first result replay")


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=on_http))
