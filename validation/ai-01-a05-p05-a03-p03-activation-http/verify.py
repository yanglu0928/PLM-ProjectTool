"""Disposable PG18/ASGI Provider activation boundary check."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.activate_provider import create_ai_provider_activate_router
from plm_assistant.modules.ai.application.activate_provider import AIProviderActivationService
from plm_assistant.modules.ai.application.provider_activation_proof import ProviderActivationProofService
from plm_assistant.modules.ai.infrastructure.provider_activation_proof_repository import SqlAlchemyProviderActivationProofRepository
from plm_assistant.modules.ai.infrastructure.provider_activation_repository import SqlAlchemyAIProviderActivationRepository
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts


parent = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p05-a01-job-read" / "verify.py"))
connect = parent["connect"]


class Sessions:
    def __init__(self, token):
        self.token = token

    def validate(self, token, *, csrf_token, require_csrf):
        if token != self.token or csrf_token != b"c" * 32 or not require_csrf:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def after_success(*, runtime, name, actor, request, ref, guard, token,
                  result_id, policies, secret):
    del actor, ref, result_id
    with connect(name) as db:
        with db.transaction():
            db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (request.secret_version_id,))
            db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (request.secret_version_id, secret))
    proof = ProviderActivationProofService(
        current=SqlAlchemyAIProviderTestSource(), secrets=SqlAlchemyAIProviderSecretProof(),
        policies=policies, latest=SqlAlchemyProviderActivationProofRepository(),
        license_guard=guard,
    )
    service = AIProviderActivationService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
        license_guard=guard, proof=proof,
        repository=SqlAlchemyAIProviderActivationRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(),
        audit=AuditService(SqlAlchemyAuditRepository()),
    )
    router = create_ai_provider_activate_router(
        sessions=Sessions(token), providers=service,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
    )
    path = f"/api/v1/admin/ai/providers/{request.provider_id}:activate"
    headers = {"cookie": "plm_session=" + token.hex(),
               "x-csrf-token": "63" * 32, "if-match": '"v0"',
               "idempotency-key": str(uuid.uuid4()), "origin": "https://plm.example.test"}
    with TestClient(create_app(ai_provider_activate_router=router),
                    base_url="https://plm.example.test") as client:
        guard.enabled = False
        assert client.post(path, headers=headers).status_code == 403
        guard.enabled = True
        first = client.post(path, headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["data"] == {"provider_id": str(request.provider_id),
                                         "state": "ACTIVE", "etag": '"v1"'}
        with connect(name) as db:
            assert db.execute("SELECT provider_state,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (request.provider_id,)).fetchone() == ("ACTIVE", 1)
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_ACTIVATED' AND target_object_id=%s", (request.provider_id,)).fetchone()[0] == 1
            db.execute("UPDATE plm.ai_providers SET provider_state='SUSPENDED',lock_version=lock_version+1 WHERE ai_provider_id=%s", (request.provider_id,))
        replay = client.post(path, headers=headers)
        assert replay.status_code == 200 and replay.json()["data"] == first.json()["data"]
        assert replay.headers["etag"] == '"v1"'
        other = client.post(path, headers={**headers, "idempotency-key": str(uuid.uuid4())})
        assert other.status_code == 409
        with connect(name) as db:
            assert db.execute("SELECT provider_state,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (request.provider_id,)).fetchone() == ("SUSPENDED", 2)
            assert db.execute("SELECT count(*) FROM plm.ai_provider_activation_results WHERE ai_provider_id=%s", (request.provider_id,)).fetchone()[0] == 1
        print("PASS: PG18/ASGI activation, License denial, immutable 200 replay, Audit and version conflict")


if __name__ == "__main__":
    parent["main"](after_success=after_success)
