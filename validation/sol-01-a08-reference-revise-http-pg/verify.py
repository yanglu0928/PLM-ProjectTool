"""Disposable PG18 PROJECT Reference revise through real ASGI/Session."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.reference_revise import create_project_reference_revise_router
from plm_assistant.modules.solution.application.create_reference_solution import CreateReferenceSolution
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.application.revise_reference_solution import ReferenceReviseService
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_create_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_created(**facts) -> int:
    request = ReferenceSourceRequest(
        facts["token"], uuid.uuid4(), "PROJECT", facts["project"],
        (facts["document_version"],), (facts["evidence"],),
        "PLM", "PROJECT_INTERNAL", {"industry": "synthetic"},
    )
    created = facts["service"].create(CreateReferenceSolution(
        request, facts["csrf"], "HTTP Reference", "http-initial-0001"))
    runtime, audit = facts["runtime"], facts["audit"]
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    service = ReferenceReviseService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=facts["license_guard"], sources=facts["sources"],
        repository=SqlAlchemyReferenceReviseRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    router = create_project_reference_revise_router(
        sessions=sessions, origins=origins, revises=service)
    path = (f"/api/v1/projects/{facts['project']}/reference-solutions/"
            f"{created.reference_solution_id}:revise")
    headers = {
        "cookie": "plm_session=" + facts["token"].hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": facts["csrf"].hex(),
        "idempotency-key": "http-revise-0001",
        "if-match": '"v0"',
    }
    body = {
        "document_version_ids": [str(facts["document_version"])],
        "evidence_ids": [str(facts["evidence"])],
        "source_project_class": "PLM",
        "deidentification_class": "PROJECT_INTERNAL",
        "applicability": {"industry": "synthetic"},
    }
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json=body).status_code == 404
    with TestClient(create_app(project_reference_revise_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.post(path, headers=headers, json=body)
        assert first.status_code == 201, first.text
        assert first.headers["etag"] == '"v1"'
        assert first.headers["cache-control"] == "no-store"
        assert first.json()["data"]["version_no"] == 2
        assert first.json()["data"]["supersedes_version_ref"] == str(
            created.reference_version_id)
        replay = client.post(path, headers=headers, json=body)
        assert replay.status_code == 201 and replay.json()["data"] == first.json()["data"]
        second = client.post(path, headers={**headers, "idempotency-key": "http-revise-0002",
                                            "if-match": '"v1"'}, json=body)
        assert second.status_code == 201, second.text
        assert second.json()["data"]["version_no"] == 3
        assert second.headers["etag"] == '"v2"'
        assert client.post(path, headers=headers, json=body).json()["data"] == first.json()["data"]
        assert client.post(path, headers={**headers, "idempotency-key": "http-stale-00001"},
                           json=body).status_code == 409
        assert client.post(path, headers={**headers,
                           "cookie": "plm_session=" + (b"u" * 32).hex(),
                           "x-csrf-token": (b"v" * 32).hex(),
                           "idempotency-key": "http-customer-001", "if-match": '"v2"'},
                           json=body).status_code == 404
        assert client.post(path, headers={**headers, "origin": "https://evil.test"},
                           json=body).status_code == 403
        assert client.post(path, headers={**headers, "if-match": 'W/"v2"'},
                           json=body).status_code == 400
    with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        root = created.reference_solution_id
        assert db.execute(
            "SELECT current_version_ref,lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s", (root,)
        ).fetchone() == (uuid.UUID(second.json()["data"]["reference_version_id"]), 2)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_revise_results "
            "WHERE reference_solution_id=%s", (root,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_REVISED' "
            "AND target_object_id=%s", (root,)).fetchone()[0] == 2
    print("SOL_01_A08_REFERENCE_REVISE_HTTP_PG_PASS")
    return 1


if __name__ == "__main__":
    fixture.main(on_created=on_created)
