"""Real ASGI/PG contract for opt-in SOL_SECTION_CREATE."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.section_create import create_section_create_router
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.create_section import SectionCreateService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager, member, token, csrf, member_token, member_csrf, **_unused) -> int:
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    outline = OutlineCreateService(
        **common, repository=SqlAlchemyOutlineCreateRepository()).create(
            CreateOutline(token, csrf, uuid.uuid4(), project,
                          "Section HTTP parent", "section-http-parent-0001"))
    dependencies = dict(**common, repository=SqlAlchemySectionCreateRepository())
    path = f"/api/v1/projects/{project}/solution-sections"
    payload = {"solution_outline_id": str(outline.solution_outline_id),
               "section_key": " Overview "}
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test", "x-csrf-token": csrf.hex(),
               "idempotency-key": "section-http-0001"}
    router = create_section_create_router(
        sessions=sessions, origins=origins,
        creates=SectionCreateService(**dependencies))
    with TestClient(create_app(solution_section_create_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.post(path, headers=headers, json=payload)
        assert first.status_code == 201, first.text
        data = first.json()["data"]
        assert data["section_key"] == "Overview"
        assert data["solution_outline_id"] == str(outline.solution_outline_id)
        assert data["project_id"] == str(project)
        assert data["section_state"] == "ACTIVE"
        assert data["current_approved_version_ref"] is None
        assert first.headers["etag"] == data["etag"] == '"v0"'
        assert first.headers["location"] == path + "/" + data["solution_section_id"]
        assert first.headers["x-trace-id"] == first.json()["trace_id"]
        assert first.headers["cache-control"] == "no-store"
        replay = client.post(path, headers=headers, json=payload)
        assert replay.status_code == 201 and replay.json()["data"] == data
        assert client.post(path, headers=headers, json={**payload, "section_key": "Other"}).status_code == 409
        assert client.post(path, headers={**headers, "idempotency-key": "section-http-0002"},
                           json=payload).status_code == 409
        member_headers = {**headers, "cookie": "plm_session=" + member_token.hex(),
                          "x-csrf-token": member_csrf.hex(),
                          "idempotency-key": "section-member-http-0001"}
        assert client.post(path, headers=member_headers, json={
            **payload, "section_key": "Member"}).status_code == 201
        assert client.post(f"/api/v1/projects/{other_project}/solution-sections",
                           headers={**headers, "idempotency-key": "section-cross-http-0001"},
                           json=payload).status_code == 404
        assert client.post(path, headers={**headers, "x-csrf-token": (b"x" * 32).hex()},
                           json=payload).status_code == 403
        assert client.post(path, headers={**headers, "origin": "https://other.test"},
                           json=payload).status_code == 403
        assert client.post(path, headers={**headers, "cookie": "plm_session=" +
                           (b"z" * 32).hex()}, json=payload).status_code == 401
        assert client.post(path, headers=headers, json={**payload, "extra": 1}).status_code == 400
        assert client.post(path, headers=headers, json={**payload,
                           "solution_outline_id": str(uuid.uuid4())}).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
        assert client.post(path, headers={**headers, "idempotency-key": "section-paused-http-0001"},
                           json={**payload, "section_key": "Paused"}).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
    denied = SectionCreateService(**{**dependencies, "license_guard": DeniedLicense()})
    with TestClient(create_app(solution_section_create_router=create_section_create_router(
            sessions=sessions, origins=origins, creates=denied)),
            base_url="https://plm.example.test") as client:
        refused = client.post(path, headers={**headers, "idempotency-key": "section-lic-http-0001"},
                              json={**payload, "section_key": "License"})
        assert refused.status_code == 403
        assert refused.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json=payload).status_code == 404
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.sol_sections WHERE project_id=%s",
                          (project,)).fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                          "action='SOL_SECTION_CREATED' AND target_project_id=%s",
                          (project,)).fetchone()[0] == 2
    return 0


if __name__ == "__main__":
    fixture.main(on_created=on_created)
    print("SOL_04_A04_SECTION_CREATE_HTTP_PG_PASS: real Session/ASGI/PG, "
          "replay, roles, CSRF, License, closed default")
