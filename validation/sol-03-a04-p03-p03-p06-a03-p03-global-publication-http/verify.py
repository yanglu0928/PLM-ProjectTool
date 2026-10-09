"""Win11 isolated ASGI/PostgreSQL GLOBAL administrator publication HTTP proof."""

from __future__ import annotations

import importlib.util
import hashlib
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.global_reference_publication import (
    create_global_reference_publication_router,
)
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateService,
)
from plm_assistant.modules.solution.application.set_global_reference_publication import (
    GlobalReferencePublicationService,
)
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityService, SetReferenceEligibility,
)
from plm_assistant.modules.solution.infrastructure.global_reference_publication_repository import (
    SqlAlchemyGlobalReferencePublicationRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_publication_http_source_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
OTHER_TOKEN = b"u" * 32


class Sessions:
    # HTTP pre-admission is synthetic; the Owner independently revalidates the
    # real persisted Auth administrator Session in the same database.
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token not in (fixture.TOKEN, OTHER_TOKEN):
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != fixture.CSRF:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


def on_qualified(*, runtime, request, sources, audit, license_guard,
                 port, **_unused) -> None:
    common = dict(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    initial = ReferenceCreateService(
        **common, repository=SqlAlchemyReferenceCreateRepository()).create(
            CreateReferenceSolution(request, fixture.CSRF,
                                    "Synthetic HTTP source name",
                                    "global-publication-http-create-0001"))
    ReferenceEligibilityService(
        **common, repository=SqlAlchemyReferenceEligibilityRepository()).set(
            SetReferenceEligibility(
                fixture.TOKEN, fixture.CSRF, uuid.uuid4(), "GLOBAL", None,
                initial.reference_solution_id, 0, "ELIGIBLE",
                "Admin reviewed source", "global-publication-http-eligible-0001"))
    owner = GlobalReferencePublicationService(
        unit_of_work=runtime.unit_of_work,
        admin=SqlAlchemyLicenseImportAccess(), license_guard=license_guard,
        sources=sources,
        repository=SqlAlchemyGlobalReferencePublicationRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    router = create_global_reference_publication_router(
        sessions=Sessions(),
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        publication=owner)
    path = (f"/api/v1/global/reference-solutions/"
            f"{initial.reference_solution_id}:set-candidate-publication")
    headers = {
        "cookie": "plm_session=" + fixture.TOKEN.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": fixture.CSRF.hex(),
        "idempotency-key": "global-publication-http-publish-0001",
    }
    body = {
        "reference_version_id": str(initial.reference_version_id),
        "expected_event_no": 0,
        "event_kind": "PUBLISH",
        "display_label": "仅合成的管理员审定标签",
        "reason": "管理员确认非敏感",
    }
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        ordinary = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Publication Ordinary','publication ordinary') RETURNING user_id"
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
            "RETURNING password_credential_id", (ordinary,)
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,"
            "active_password_credential_id=%s,state='ENABLED',"
            "deployment_role='NONE' WHERE user_id=%s",
            (credential, ordinary))
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) "
            "VALUES (%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
            "statement_timestamp()+interval '2 hours')",
            (hashlib.sha256(OTHER_TOKEN).digest(),
             hashlib.sha256(fixture.CSRF).digest(), ordinary))
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(path, headers=headers, json=body).status_code == 404
    with TestClient(create_app(global_reference_publication_router=router),
                    base_url="https://plm.example.test") as client:
        assert client.post(path, headers={**headers, "origin": "https://evil.test"},
                           json=body).status_code == 403
        assert client.post(path, headers={k: v for k, v in headers.items()
                                          if k != "cookie"}, json=body).status_code == 401
        assert client.post(path, headers={**headers,
                                          "cookie": "plm_session=" + OTHER_TOKEN.hex()},
                           json=body).status_code == 404
        assert client.post(path, headers=headers, json={**body, "extra": 1}).status_code == 400
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-trace-id"] == response.json()["trace_id"]
        data = response.json()["data"]
        assert data["display_label"] == "仅合成的管理员审定标签"
        assert data["event_no"] == 1 and data["event_kind"] == "PUBLISH"
        assert "Synthetic HTTP source name" not in response.text
        assert "source_fingerprint" not in response.text
        replay = client.post(path, headers=headers, json=body)
        assert replay.status_code == 200 and replay.json()["data"] == data
        stale = client.post(path, headers={**headers,
                                          "idempotency-key": "global-publication-http-stale-0001"},
                            json=body)
        assert stale.status_code == 409
        revoke = {**body, "expected_event_no": 1,
                  "event_kind": "REVOKE", "display_label": None,
                  "reason": "管理员撤回"}
        response = client.post(path, headers={**headers,
                                              "idempotency-key": "global-publication-http-revoke-0001"},
                               json=revoke)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["event_no"] == 2
        assert response.json()["data"]["display_label"] is None
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.sol_global_reference_publication_events "
            "WHERE reference_solution_id=%s", (initial.reference_solution_id,)
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
            "AND action='SOL_GLOBAL_REFERENCE_PUBLICATION_SET'",
            (initial.reference_solution_id,)).fetchone()[0] == 2
    print("SOL_03_A04_P03_P03_P06_A03_P03_PUBLICATION_HTTP_PG_PASS: "
          "default 404, real Owner/PG publish/revoke, original replay, "
          "Origin/Session/non-admin/body/stale refusal, minimal response and Audit")


if __name__ == "__main__":
    fixture.main(on_qualified=on_qualified)
