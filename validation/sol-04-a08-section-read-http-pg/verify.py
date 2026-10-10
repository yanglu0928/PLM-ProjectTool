"""Win11 isolated ASGI/PG proof for opt-in SolutionSection detail GET."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.section_read import create_section_read_router
from plm_assistant.modules.solution.application.read_section import SectionReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_read_owner_fixture",
    ROOT / "validation/sol-04-a07-section-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               member, token, member_token, create_router_factory=None, **kwargs):
    prior.on_created(port=port, runtime=runtime, audit=audit,
                     license_guard=license_guard, project=project,
                     other_project=other_project, token=token,
                     member=member, member_token=member_token, **kwargs)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        section_id, outline_id = db.execute(
            "SELECT solution_section_id,solution_outline_id FROM plm.sol_sections "
            "WHERE project_id=%s AND section_key='Scope'",
            (project,)).fetchone()
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    common = dict(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemySectionReadRepository())
    origins = LoginOriginPolicy(["https://plm.example.test"])
    router = (create_section_read_router(
        sessions=sessions, origins=origins,
        reads=SectionReadService(**common, license_guard=license_guard))
        if create_router_factory is None else create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard))
    path = f"/api/v1/projects/{project}/solution-sections/{section_id}"
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.get(path, headers=headers).status_code == 404
    with TestClient(create_app(solution_section_read_router=router),
                    base_url="https://plm.example.test") as client:
        assert client.post(f"/api/v1/projects/{project}/solution-sections",
                           headers=headers, json={}).status_code == 404
        good = client.get(path, headers=headers)
        assert good.status_code == 200, good.text
        data = good.json()["data"]
        assert data["solution_section_id"] == str(section_id)
        assert data["solution_outline_id"] == str(outline_id)
        assert data["project_id"] == str(project) and data["section_key"] == "Scope"
        assert data["section_state"] == "ACTIVE"
        assert data["current_approved_version_ref"] is None
        assert good.headers["etag"] == data["etag"] == '"v0"'
        assert good.headers["cache-control"] == "no-store"
        assert good.headers["x-trace-id"] == good.json()["trace_id"]
        assert client.get(path, headers={"cookie": "plm_session=" + member_token.hex(),
                                         "origin": "https://plm.example.test"}).status_code == 200
        assert client.get(path, headers={"cookie": "plm_session=" + (b"u" * 32).hex(),
                                         "origin": "https://plm.example.test"}).status_code == 200
        assert client.get(path, headers={}).status_code == 401
        assert client.get(path, headers={**headers, "origin": "https://evil.test"}).status_code == 403
        assert client.get(path + "?x=1", headers=headers).status_code == 400
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert client.get(path.replace(str(section_id), str(uuid.uuid4())),
                          headers=headers).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
        assert client.get(path, headers={"cookie": "plm_session=" + member_token.hex(),
                                         "origin": "https://plm.example.test"}).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
    denied = SectionReadService(**common, license_guard=DeniedLicense())
    denied_router = (create_section_read_router(
        sessions=sessions, origins=origins, reads=denied)
        if create_router_factory is None else create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=DeniedLicense()))
    with TestClient(create_app(solution_section_read_router=denied_router),
                    base_url="https://plm.example.test") as client:
        result = client.get(path, headers=headers)
        assert result.status_code == 403
        assert result.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    return 0


if __name__ == "__main__":
    prior.fixture.main(on_created=on_created)
    print("SOL_04_A08_SECTION_READ_HTTP_PG_PASS: default closed, "
          "real ASGI/Session/PG, ETag, members, isolation and License")
