"""Real ASGI/PG PROJECT Reference POST over synthetic private source bytes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import create_windows_project_reference_create_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.reference_create import create_project_reference_create_router
from plm_assistant.modules.solution.application.create_reference_solution import ReferenceCreateService
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository


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


def on_created(*, port, scratch, locator, content, runtime, service, sources, audit, project,
               other_project, document_version, evidence, token, csrf,
               member_token, member_csrf,
               documents, downloads, parse_results,
               **_unused) -> None:
    origins = LoginOriginPolicy(["https://plm.example.test"])
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit,
    )
    router = create_windows_project_reference_create_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=_unused["license_guard"], audit=audit,
        documents=documents, downloads=downloads,
        parse_results=parse_results)
    path = f"/api/v1/projects/{project}/reference-solutions"
    body = {
        "name": "HTTP Project Reference",
        "document_version_ids": [str(document_version)],
        "evidence_ids": [str(evidence)],
        "source_project_class": "PLM",
        "deidentification_class": "PROJECT_INTERNAL",
        "applicability": {"industry": "synthetic"},
    }
    headers = {
        "cookie": "plm_session=" + token.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": csrf.hex(),
        "idempotency-key": "h" * 16,
    }
    with TestClient(create_app(project_reference_create_router=router),
                    base_url="https://plm.example.test") as client:
        created = client.post(path, headers=headers, json=body)
        assert created.status_code == 201, created.text
        result = created.json()["data"]
        assert result["scope"] == "PROJECT" and result["project_id"] == str(project)
        assert result["eligibility_state"] == "REFERENCE_ONLY"
        assert result["version_state"] == "DRAFT"
        assert created.headers["etag"] == '"v0"'
        assert created.headers["location"].endswith(result["reference_solution_id"])
        assert created.headers["x-trace-id"] == created.json()["trace_id"]
        member_headers = {**headers,
            "cookie": "plm_session=" + member_token.hex(),
            "x-csrf-token": member_csrf.hex(),
            "idempotency-key": "i" * 16,
        }
        member_created = client.post(path, headers=member_headers,
                                     json={**body, "name": "Member HTTP Reference"})
        assert member_created.status_code == 201, member_created.text
        assert member_created.json()["data"]["created_by"] == str(_unused["member"])
        replay = client.post(path, headers=headers, json=body)
        assert replay.status_code == 201 and replay.json()["data"] == result
        assert client.post(path, headers=headers,
                           json={**body, "name": "Different"}).status_code == 409
        assert client.post(f"/api/v1/projects/{other_project}/reference-solutions",
                           headers=headers, json=body).status_code == 404
        assert client.post(path, headers={**headers, "x-csrf-token": (b"x" * 32).hex()},
                           json=body).status_code == 403
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (_unused["manager"], project))
        assert client.post(path, headers=headers, json=body).status_code == 404
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (_unused["manager"], project))
        source_file = scratch / "private-documents" / locator
        source_file.write_bytes(b"X" * len(content))
        tampered = client.post(path, headers={**headers, "idempotency-key": "t" * 16},
                               json=body)
        assert tampered.status_code == 503, tampered.text
        source_file.write_bytes(content)

    denied = ReferenceCreateService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=DeniedLicense(), sources=sources,
        repository=SqlAlchemyReferenceCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    denied_router = create_project_reference_create_router(
        sessions=sessions, origins=origins, creates=denied)
    with TestClient(create_app(project_reference_create_router=denied_router),
                    base_url="https://plm.example.test") as client:
        refused = client.post(path, headers={**headers, "idempotency-key": "l" * 16},
                              json=body)
        assert refused.status_code == 403 and refused.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"


def main() -> None:
    project_fixture.main(on_created=on_created)
    print("SOL_01_A04_P03_P02_P04_PROJECT_REFERENCE_HTTP_PG_PASS: real "
          "SessionService, ASGI, PG, private file, replay, authorization, "
          "CSRF and denied License")


if __name__ == "__main__":
    main()
