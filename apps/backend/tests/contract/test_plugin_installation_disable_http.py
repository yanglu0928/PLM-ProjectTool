from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError, SessionPrincipal
from plm_assistant.modules.plugin.api.installation_disable import (
    create_plugin_installation_disable_router,
)
from plm_assistant.modules.plugin.application.installation_disable import (
    PluginInstallationDisableError, PluginInstallationDisableResult,
)


class _Sessions:
    def __init__(self, actor: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        self.principal = SessionPrincipal(
            uuid.uuid4(), actor, 1, now + timedelta(hours=8),
            now + timedelta(minutes=30),
        )
        self.fail = None

    def validate(self, _token, *, csrf_token=None, require_csrf=False):
        if require_csrf and self.fail:
            raise SessionError(self.fail)
        return self.principal


class _DisableService:
    def __init__(self, actor: uuid.UUID, installation_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        self.actor = actor
        self.installation_id = installation_id
        self.result = PluginInstallationDisableResult(
            uuid.uuid4(), installation_id, actor, uuid.uuid4(), 4, 5,
            "DISABLED", True, now,
        )
        self.calls = []
        self.fail = None

    def disable(self, command, *, session_token, csrf_token, idempotency_key):
        self.calls.append((command, session_token, csrf_token, idempotency_key))
        if self.fail:
            raise PluginInstallationDisableError(self.fail)
        return self.result


class PluginInstallationDisableHttpTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid.uuid4()
        self.installation_id = uuid.uuid4()
        self.sessions = _Sessions(self.actor)
        self.disables = _DisableService(self.actor, self.installation_id)
        router = create_plugin_installation_disable_router(
            sessions=self.sessions,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            disables=self.disables,
        )
        self.client = TestClient(
            create_app(plugin_installation_disable_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = (
            f"/api/v1/admin/plugins/installations/"
            f"{self.installation_id}:disable"
        )
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + "ab" * 32,
            "x-csrf-token": "cd" * 32,
            "if-match": '"v4"',
            "idempotency-key": "stable-plugin-disable-key",
        }

    def test_response_is_exact_disabled_snapshot_and_default_is_closed(self):
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["installation_state"], "DISABLED")
        self.assertEqual(data["lock_version"], 5)
        self.assertEqual(data["etag"], '"v5"')
        self.assertEqual(data["enabled_operations"], [])
        self.assertEqual(response.headers["etag"], '"v5"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(self.disables.calls[0][0].expected_lock_version, 4)
        self.assertEqual(self.disables.calls[0][3], self.headers["idempotency-key"])
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path, headers=self.headers).status_code, 404)

    def test_preconditions_and_empty_body_fail_before_owner(self):
        for headers, status in (
            ({k: v for k, v in self.headers.items() if k != "if-match"}, 428),
            ({**self.headers, "if-match": 'W/"v4"'}, 400),
            ({k: v for k, v in self.headers.items() if k != "idempotency-key"}, 422),
            ({**self.headers, "origin": "https://evil.example"}, 403),
        ):
            self.assertEqual(self.client.post(self.path, headers=headers).status_code, status)
        self.assertEqual(self.client.post(self.path + "?debug=1", headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post(self.path, headers=self.headers, content=b"{}").status_code, 400)
        self.assertEqual(self.disables.calls, [])

    def test_session_and_owner_errors_are_safe(self):
        self.sessions.fail = "AUTH_ACCESS_DENIED"
        self.assertEqual(self.client.post(self.path, headers=self.headers).status_code, 403)
        self.sessions.fail = None
        for code, status in (
            ("RESOURCE_NOT_FOUND", 404),
            ("CONFLICT_VERSION", 409),
            ("CONFLICT_STATE", 409),
            ("CONFLICT_IDEMPOTENCY", 409),
            ("LICENSE_OPERATION_DENIED", 403),
            ("PLUGIN_DISABLE_UNAVAILABLE", 503),
        ):
            self.disables.fail = code
            response = self.client.post(self.path, headers=self.headers)
            self.assertEqual(response.status_code, status)
            self.assertNotIn("private", response.text)


if __name__ == "__main__":
    unittest.main()
