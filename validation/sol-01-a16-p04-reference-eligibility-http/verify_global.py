"""Win11 disposable PG18 GLOBAL Reference eligibility real ASGI/Session."""

from __future__ import annotations

import importlib.util
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
from plm_assistant.modules.solution.api.reference_eligibility import create_global_reference_eligibility_router
from plm_assistant.modules.solution.application.create_reference_solution import CreateReferenceSolution, ReferenceCreateService
from plm_assistant.modules.solution.application.set_reference_eligibility import ReferenceEligibilityService
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository


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
    initial = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(
                request, fixture.CSRF, "HTTP Global Reference",
                "global-eligibility-http-create-0001"))
    assert initial.deidentification_confirmation_id == confirmed.confirmation_id
    service = ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository())
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    router = create_global_reference_eligibility_router(
        sessions=sessions, origins=LoginOriginPolicy(["https://plm.example.test"]),
        eligibility=service)
    path = (f"/api/v1/global/reference-solutions/"
            f"{initial.reference_solution_id}:set-eligibility")
    headers = {
        "cookie": "plm_session=" + fixture.TOKEN.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": fixture.CSRF.hex(),
        "idempotency-key": "global-eligibility-http-0001",
        "if-match": '"v0"',
    }
    body = {"eligibility_state": "ELIGIBLE", "reason": "Admin verified current sources"}
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json=body).status_code == 404
    with TestClient(create_app(global_reference_eligibility_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.post(path, headers=headers, json=body)
        assert first.status_code == 200, first.text
        assert first.headers["etag"] == '"v1"'
        assert first.json()["data"]["scope"] == "GLOBAL"
        assert first.json()["data"]["project_id"] is None
        assert client.post(path, headers=headers, json=body).json()["data"] == first.json()["data"]
        restricted = client.post(
            path, headers={**headers, "if-match": '"v1"',
                            "idempotency-key": "global-eligibility-http-0002"},
            json={"eligibility_state": "RESTRICTED", "reason": "Admin review"})
        assert restricted.status_code == 200 and restricted.headers["etag"] == '"v2"'
        assert client.post(path, headers=headers, json=body).json()["data"] == first.json()["data"]
        assert client.post(
            path, headers={**headers, "idempotency-key": "global-eligibility-stale-0001"},
            json=body).status_code == 409
        assert client.post(
            path, headers={**headers, "cookie": "plm_session=" + (b"x" * 32).hex(),
                            "x-csrf-token": (b"y" * 32).hex(),
                            "idempotency-key": "global-eligibility-stranger-0001",
                            "if-match": '"v2"'},
            json=body).status_code == 401
        assert client.post(path, headers={**headers, "origin": "https://evil.test"},
                           json=body).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        root = initial.reference_solution_id
        assert db.execute(
            "SELECT eligibility_state,lock_version FROM plm.sol_reference_solutions "
            "WHERE reference_solution_id=%s", (root,)).fetchone() == ("RESTRICTED", 2)
        assert db.execute(
            "SELECT count(*) FROM plm.sol_reference_eligibility_events "
            "WHERE reference_solution_id=%s", (root,)).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE target_object_id=%s AND action='SOL_REFERENCE_ELIGIBILITY_SET'",
            (root,)).fetchone()[0] == 2
    print("SOL_01_A16_P04_REFERENCE_ELIGIBILITY_GLOBAL_HTTP_PG_PASS")


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
