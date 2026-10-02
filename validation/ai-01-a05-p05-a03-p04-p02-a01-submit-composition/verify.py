"""Disposable PG18/ASGI check of closed Windows Provider Test submit composition."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_ai_provider_test_submit import (
    WindowsAIProviderTestSubmitStartupError,
    create_windows_ai_provider_test_submit_router,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


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
    del actor, ref, result_id, policies
    with connect(name) as db:
        with db.transaction():
            db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (request.secret_version_id,))
            db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (request.secret_version_id, secret))
    settings = BootstrapSettings(
        data_root=Path.cwd(), ai_probe_policies=({
            "reference": "endpoint.synthetic.v1", "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://probe.example.test/v1/chat",
            "model_key": "synthetic-chat", "data_region": "cn-beijing",
            "egress_class": "SYNTHETIC",
        },),
    )
    args = dict(runtime=runtime, sessions=Sessions(token),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                license_guard=guard, audit=AuditService(SqlAlchemyAuditRepository()))
    try:
        create_windows_ai_provider_test_submit_router(
            settings=BootstrapSettings(data_root=Path.cwd()), **args)
    except WindowsAIProviderTestSubmitStartupError:
        pass
    else:
        raise AssertionError("missing policy did not fail closed")
    router = create_windows_ai_provider_test_submit_router(settings=settings, **args)
    path = f"/api/v1/admin/ai/providers/{request.provider_id}:test"
    headers = {"cookie": "plm_session=" + token.hex(),
               "x-csrf-token": "63" * 32, "if-match": '"v0"',
               "idempotency-key": str(uuid.uuid4()), "origin": "https://plm.example.test"}
    with TestClient(create_app(), base_url="https://plm.example.test") as default:
        assert default.post(path, headers=headers).status_code == 404
    with TestClient(create_app(ai_provider_test_router=router),
                    base_url="https://plm.example.test") as client:
        guard.enabled = False
        assert client.post(path, headers=headers).status_code == 403
        guard.enabled = True
        first = client.post(path, headers=headers)
        assert first.status_code == 202, first.text
        replay = client.post(path, headers=headers)
        assert replay.status_code == 202 and replay.json()["data"] == first.json()["data"]
        job_id = uuid.UUID(first.json()["data"]["job_id"])
        with connect(name) as db:
            pair = db.execute(
                "SELECT j.payload_refs,e.payload_refs FROM plm.job_jobs j "
                "JOIN plm.job_outbox_events e ON e.idempotency_key=j.idempotency_key "
                "WHERE j.job_id=%s", (job_id,),
            ).fetchone()
            assert pair and pair[1] == dict(pair[0], job_id=str(job_id))
            assert set(pair[0]) == {"provider_id", "config_id", "secret_version_id",
                                    "policy_sha256", "probe_id"}
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_TEST_REQUESTED' AND target_object_id=%s", (request.provider_id,)).fetchone()[0] == 1
        print("PASS: PG18/ASGI closed default, missing policy, License, 202 Job/Outbox/Audit and replay")


if __name__ == "__main__":
    parent["main"](after_success=after_success)
