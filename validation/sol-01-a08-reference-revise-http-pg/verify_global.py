"""Disposable PG18 GLOBAL Reference revise through real ASGI/Session."""

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
from plm_assistant.modules.solution.api.reference_revise import create_global_reference_revise_router
from plm_assistant.modules.solution.application.create_reference_solution import CreateReferenceSolution, ReferenceCreateService
from plm_assistant.modules.solution.application.revise_reference_solution import ReferenceReviseService
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_source_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_qualified(*, runtime, request, sources, audit, license_guard,
                 confirmed, port, **_unused) -> None:
    auth = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=auth, license_guard=license_guard,
        sources=sources, receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    creates = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository())
    revises = ReferenceReviseService(
        **common, repository=SqlAlchemyReferenceReviseRepository())
    initial = creates.create(CreateReferenceSolution(
        request, fixture.CSRF, "Global HTTP Reference", "global-http-create-001"))
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    router = create_global_reference_revise_router(
        sessions=sessions, origins=LoginOriginPolicy(["https://plm.example.test"]),
        revises=revises)
    path = f"/api/v1/global/reference-solutions/{initial.reference_solution_id}:revise"
    headers = {
        "cookie": "plm_session=" + fixture.TOKEN.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": fixture.CSRF.hex(),
        "if-match": '"v0"',
        "idempotency-key": "global-http-revise-001",
    }
    body = {
        "document_version_ids": [str(item) for item in request.document_version_ids],
        "evidence_ids": [str(item) for item in request.evidence_ids],
        "source_project_class": request.source_project_class,
        "deidentification_class": request.deidentification_class,
        "applicability": request.applicability,
    }
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json=body).status_code == 404
    with TestClient(create_app(global_reference_revise_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.post(path, headers=headers, json=body)
        assert first.status_code == 201, first.text
        assert first.json()["data"]["version_no"] == 2
        assert first.json()["data"]["scope"] == "GLOBAL"
        assert first.json()["data"]["project_id"] is None
        assert client.post(path, headers=headers, json=body).json()["data"] == first.json()["data"]
        assert client.post(path, headers={**headers, "idempotency-key": "global-http-change-01",
                            "if-match": '"v1"'}, json={**body,
                            "evidence_ids": [str(request.evidence_ids[0])]}).status_code == 404
        assert client.post(path, headers={**headers, "if-match": 'W/"v0"'},
                           json=body).status_code == 400
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT deidentification_confirmation_id FROM plm.sol_reference_versions "
            "WHERE reference_version_id=%s",
            (uuid.UUID(first.json()["data"]["reference_version_id"]),)
        ).fetchone()[0] == confirmed.confirmation_id
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_revise_results "
            "WHERE reference_solution_id=%s", (initial.reference_solution_id,)
        ).fetchone()[0] == 1
    print("SOL_01_A08_REFERENCE_REVISE_GLOBAL_HTTP_PG_PASS")


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
