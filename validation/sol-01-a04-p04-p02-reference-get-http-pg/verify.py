"""Disposable PG18 and real SessionService proof for PROJECT Reference GET."""

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
from plm_assistant.modules.solution.api.reference_read import create_project_reference_read_router
from plm_assistant.modules.solution.application.read_reference import ReferenceReadService
from plm_assistant.modules.solution.infrastructure.reference_read_repository import SqlAlchemyReferenceReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
project_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def _reader(runtime, license_guard):
    return ReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyReferenceReadRepository())


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager, member, created, member_created, global_version,
               document_version, evidence, token, member_token, **_unused) -> int:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    router = create_project_reference_read_router(
        sessions=sessions, origins=origins,
        reads=_reader(runtime, license_guard))
    path = (f"/api/v1/projects/{project}/reference-solutions/"
            f"{created.reference_solution_id}")
    headers = {"cookie": "plm_session=" + token.hex(),
               "origin": "https://plm.example.test"}
    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex()}
    with TestClient(create_app(project_reference_read_router=router),
                    base_url="https://plm.example.test") as client:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["reference_solution_id"] == str(created.reference_solution_id)
        assert data["reference_version_id"] == str(created.reference_version_id)
        assert data["document_version_ids"] == [str(document_version)]
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            (expected_document_id,) = db.execute(
                "SELECT document_id FROM plm.doc_document_versions "
                "WHERE document_version_id=%s", (document_version,)).fetchone()
        assert data["document_refs"] == [{
            "document_id": str(expected_document_id),
            "document_version_id": str(document_version)}]
        assert data["evidence_ids"] == [str(evidence)]
        assert data["source_fingerprint"] == created.source_fingerprint.hex()
        assert data["eligibility_state"] == "REFERENCE_ONLY"
        assert response.headers["etag"] == '"v0"'
        assert response.headers["x-trace-id"] == response.json()["trace_id"]
        assert client.get(path, headers=member_headers).status_code == 200
        customer_headers = {**headers, "cookie": "plm_session=" + (b"u" * 32).hex()}
        assert client.get(path, headers=customer_headers).status_code == 200
        assert client.get(
            f"/api/v1/projects/{project}/reference-solutions/"
            f"{member_created.reference_solution_id}",
            headers=member_headers).json()["data"]["evidence_ids"] == []
        assert client.get(path.replace(str(project), str(other_project)),
                          headers=headers).status_code == 404
        assert client.get(path.replace(str(created.reference_solution_id),
                                       str(uuid.uuid4())),
                          headers=headers).status_code == 404
        assert client.get(path + "?scope=GLOBAL", headers=headers).status_code == 400
        assert client.get(path, headers={**headers,
            "origin": "https://evil.test"}).status_code == 403
        assert client.get(path).status_code == 401
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
        assert client.get(path, headers=member_headers).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
            db.execute("INSERT INTO plm.sol_reference_document_refs("
                       "reference_version_id,reference_solution_id,scope,"
                       "document_version_id,ordinal) VALUES (%s,%s,'PROJECT',%s,2)",
                       (created.reference_version_id, created.reference_solution_id,
                        global_version))
        corrupt = client.get(path, headers=headers)
        assert corrupt.status_code == 503, corrupt.text
        assert "PRIVATE KEY" not in corrupt.text

    denied_router = create_project_reference_read_router(
        sessions=sessions, origins=origins,
        reads=_reader(runtime, DeniedLicense()))
    with TestClient(create_app(project_reference_read_router=denied_router),
                    base_url="https://plm.example.test") as client:
        response = client.get(path, headers=headers)
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    return 0


def main() -> None:
    project_fixture.main(on_created=on_created)
    print("SOL_01_A04_P04_P02_REFERENCE_GET_HTTP_PG_PASS: real SessionService/ASGI/"
          "PG, fixed refs, PM/IM/customer, project isolation, revoked member, "
          "license and corrupt source projection denied")


if __name__ == "__main__":
    main()
