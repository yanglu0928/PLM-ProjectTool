"""Win11 disposable PG18 PROJECT Reference eligibility real ASGI/Session."""

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
from plm_assistant.modules.solution.api.reference_eligibility import create_project_reference_eligibility_router
from plm_assistant.modules.solution.application.set_reference_eligibility import ReferenceEligibilityService
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "project_reference_create_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_created(*, router_factory=None, **facts) -> None:
    runtime, audit = facts["runtime"], facts["audit"]
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    service = ReferenceEligibilityService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=facts["license_guard"], sources=facts["sources"],
        repository=SqlAlchemyReferenceEligibilityRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    origins = LoginOriginPolicy(["https://plm.example.test"])
    router = (create_project_reference_eligibility_router(
        sessions=sessions, origins=origins, eligibility=service)
        if router_factory is None else router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=facts["license_guard"], audit=audit,
            documents=facts["documents"], downloads=facts["downloads"],
            parse_results=facts["parse_results"]))
    root = facts["created"].reference_solution_id
    path = (f"/api/v1/projects/{facts['project']}/reference-solutions/"
            f"{root}:set-eligibility")
    headers = {
        "cookie": "plm_session=" + facts["token"].hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": facts["csrf"].hex(),
        "idempotency-key": "eligibility-http-project-0001",
        "if-match": '"v0"',
    }
    body = {"eligibility_state": "ELIGIBLE", "reason": "Manager verified sources"}
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json=body).status_code == 404
    with TestClient(create_app(project_reference_eligibility_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.post(path, headers=headers, json=body)
        assert first.status_code == 200, first.text
        assert first.headers["etag"] == '"v1"'
        assert first.json()["data"]["reference_version_id"] == str(
            facts["created"].reference_version_id)
        assert first.json()["data"]["eligibility_state"] == "ELIGIBLE"
        assert client.post(path, headers=headers, json=body).json()["data"] == first.json()["data"]
        restricted = client.post(
            path, headers={**headers, "if-match": '"v1"',
                            "idempotency-key": "eligibility-http-project-0002"},
            json={"eligibility_state": "RESTRICTED", "reason": "Review pending"})
        assert restricted.status_code == 200 and restricted.headers["etag"] == '"v2"'
        assert client.post(path, headers=headers, json=body).json()["data"] == first.json()["data"]
        assert client.post(
            path, headers={**headers, "idempotency-key": "eligibility-stale-0001"},
            json=body).status_code == 409
        assert client.post(
            path, headers={**headers, "cookie": "plm_session=" + facts["member_token"].hex(),
                            "x-csrf-token": facts["member_csrf"].hex(),
                            "if-match": '"v2"',
                            "idempotency-key": "eligibility-member-0001"},
            json=body).status_code == 404
        assert client.post(path, headers={**headers, "origin": "https://evil.test"},
                           json=body).status_code == 403
        assert client.post(path, headers={**headers, "if-match": 'W/"v2"'},
                           json=body).status_code == 400
    with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
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
    print("SOL_01_A16_P04_REFERENCE_ELIGIBILITY_PROJECT_HTTP_PG_PASS")
    return None


if __name__ == "__main__":
    fixture.main(on_created=on_created)
