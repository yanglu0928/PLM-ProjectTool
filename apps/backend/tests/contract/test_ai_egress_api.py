from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.egress import create_ai_egress_router
from plm_assistant.modules.ai.application.egress_authorization import (
    AuthorizeEgress,
    EgressAuthorizationError,
    EgressAuthorizationView,
    EgressAuthorizeResult,
    EgressRevokeResult,
    RevokeEgress,
)
from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview,
    EgressPreviewError,
    EgressPreviewQuery,
    EgressPreviewSourceView,
    EgressPreviewView,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


NOW = datetime(2026, 10, 3, 4, 5, 6, tzinfo=timezone.utc)


class Sessions:
    valid = True

    def validate(self, token: bytes, *, csrf_token: bytes | None = None,
                 require_csrf: bool = False) -> object:
        if (not self.valid or token != b"a" * 32
                or (require_csrf and csrf_token != b"c" * 32)):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Previews:
    def __init__(self, view: EgressPreviewView) -> None:
        self.view = view
        self.failure: str | None = None
        self.create_command: CreateEgressPreview | None = None
        self.get_query: EgressPreviewQuery | None = None
        self.key: str | None = None

    def create(self, command: CreateEgressPreview, *, idempotency_key: str) -> EgressPreviewView:
        self.create_command, self.key = command, idempotency_key
        if self.failure:
            raise EgressPreviewError(self.failure)
        return self.view

    def get(self, query: EgressPreviewQuery, *, preview_id: uuid.UUID) -> EgressPreviewView:
        self.get_query = query
        if self.failure:
            raise EgressPreviewError(self.failure)
        if preview_id != self.view.preview_id:
            raise EgressPreviewError("RESOURCE_NOT_FOUND")
        return self.view


class Authorizations:
    def __init__(self, view: EgressAuthorizationView) -> None:
        self.view = view
        self.failure: str | None = None
        self.authorize_command: AuthorizeEgress | None = None
        self.revoke_command: RevokeEgress | None = None
        self.key: str | None = None

    def authorize(self, command: AuthorizeEgress, *, idempotency_key: str) -> EgressAuthorizeResult:
        self.authorize_command, self.key = command, idempotency_key
        if self.failure:
            raise EgressAuthorizationError(self.failure)
        return EgressAuthorizeResult(uuid.uuid4(), self.view, uuid.uuid4(), uuid.uuid4())

    def revoke(self, command: RevokeEgress, *, idempotency_key: str) -> EgressRevokeResult:
        self.revoke_command, self.key = command, idempotency_key
        if self.failure:
            raise EgressAuthorizationError(self.failure)
        return EgressRevokeResult(
            uuid.uuid4(), command.authorization_id, uuid.uuid4(), uuid.uuid4(),
            "ProjectManager", uuid.uuid4(), uuid.uuid4(), "REVOKED", 1, NOW,
        )


class AIEgressApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id, self.preview_id = uuid.uuid4(), uuid.uuid4()
        self.provider_id, self.config_id, self.model_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        self.resource_id, self.version_id = uuid.uuid4(), uuid.uuid4()
        self.authorization_id = uuid.uuid4()
        self.preview = EgressPreviewView(
            self.preview_id, self.project_id, "TASK.CAPABILITY_EXTRACT", "AI_TASK",
            self.provider_id, self.config_id, self.model_id, "cn-beijing",
            ("CUSTOMER_DOCUMENT",),
            (EgressPreviewSourceView("DOCUMENT_VERSION", self.resource_id, self.version_id),),
            "egress.minimal.v1", 1, 4096, 512, 2, b"p" * 32, b"s" * 32,
            ("CUSTOMER_DATA_EXTERNAL",), NOW, NOW + timedelta(minutes=30),
        )
        self.authorization = EgressAuthorizationView(
            self.authorization_id, self.preview_id, self.project_id,
            self.preview.purpose_ref, self.preview.operation_type, self.provider_id,
            self.config_id, self.model_id, "cn-beijing", ("CUSTOMER_DOCUMENT",),
            "egress.minimal.v1", 1, 4096, 512, 2, b"p" * 32, b"s" * 32,
            uuid.uuid4(), "ProjectManager", NOW, NOW + timedelta(minutes=20),
            "AUTHORIZED", 0,
        )
        self.sessions = Sessions()
        self.previews, self.authorizations = Previews(self.preview), Authorizations(self.authorization)
        router = create_ai_egress_router(
            sessions=self.sessions, previews=self.previews,
            authorizations=self.authorizations,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_egress_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.preview_path = f"/api/v1/projects/{self.project_id}/egress-previews"
        self.preview_body = {
            "purpose_ref": "TASK.CAPABILITY_EXTRACT", "operation_type": "AI_TASK",
            "provider_id": str(self.provider_id), "model_id": str(self.model_id),
            "source_refs": [{
                "resource_type": "DOCUMENT_VERSION", "resource_id": str(self.resource_id),
                "version_id": str(self.version_id),
            }],
            "allowed_data_categories": ["CUSTOMER_DOCUMENT"],
            "minimal_payload_policy_ref": "egress.minimal.v1",
            "estimated_record_count": 1, "max_payload_bytes": 4096,
            "max_input_tokens": 512, "max_retry_attempts": 2,
            "payload_fingerprint": (b"p" * 32).hex(),
        }
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test",
        }
        self.authorize_body = {
            "expected_preview_fingerprint": self.preview.preview_fingerprint.hex(),
            "allowed_data_categories": ["CUSTOMER_DOCUMENT"],
            "max_record_count": 1, "max_payload_bytes": 4096,
            "max_input_tokens": 512, "max_retry_attempts": 2,
            "valid_until": "2026-10-03T04:25:06Z",
        }

    def test_default_closed_and_preview_create_get_safe_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(
                self.preview_path, json=self.preview_body, headers=self.headers,
            ).status_code, 404)
            self.assertEqual(default.get(
                self.preview_path + "/" + str(self.preview_id),
                headers={"cookie": self.headers["cookie"]},
            ).status_code, 404)
            self.assertEqual(default.post(
                self.preview_path + "/" + str(self.preview_id) + ":authorize",
                json=self.authorize_body, headers={**self.headers, "if-match": '"v0"'},
            ).status_code, 404)
            self.assertEqual(default.post(
                f"/api/v1/projects/{self.project_id}/egress-authorizations/"
                f"{self.authorization_id}:revoke",
                json={"reason_code": "USER_REVOKED", "reason_summary": "No longer needed"},
                headers={**self.headers, "if-match": '"v0"'},
            ).status_code, 404)
        created = self.client.post(self.preview_path, json=self.preview_body, headers=self.headers)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.headers["cache-control"], "no-store")
        self.assertEqual(created.headers["location"], self.preview_path + "/" + str(self.preview_id))
        self.assertEqual(created.json()["data"]["preview_fingerprint"],
                         self.preview.preview_fingerprint.hex())
        self.assertEqual(self.previews.create_command.source_refs[0].version_id, self.version_id)
        self.assertEqual(self.previews.create_command.payload_fingerprint, b"p" * 32)
        detail = self.client.get(
            self.preview_path + "/" + str(self.preview_id),
            headers={"cookie": self.headers["cookie"]},
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["source_refs"][0]["resource_id"],
                         str(self.resource_id))
        for forbidden in ("api_key", "secret", "customer正文", "traceback"):
            self.assertNotIn(forbidden, detail.text.lower())

    def test_authorize_and_revoke_contracts(self) -> None:
        authorize_path = self.preview_path + "/" + str(self.preview_id) + ":authorize"
        authorized = self.client.post(
            authorize_path, json=self.authorize_body,
            headers={**self.headers, "if-match": '"v0"'},
        )
        self.assertEqual(authorized.status_code, 201)
        self.assertEqual(authorized.headers["etag"], '"v0"')
        self.assertEqual(authorized.json()["data"]["authorization_id"],
                         str(self.authorization_id))
        self.assertEqual(authorized.json()["data"]["preview_fingerprint"],
                         self.preview.preview_fingerprint.hex())
        self.assertEqual(self.authorizations.authorize_command.valid_until,
                         datetime(2026, 10, 3, 4, 25, 6, tzinfo=timezone.utc))
        revoke_path = (
            f"/api/v1/projects/{self.project_id}/egress-authorizations/"
            f"{self.authorization_id}:revoke"
        )
        revoked = self.client.post(
            revoke_path, json={"reason_code": "USER_REVOKED", "reason_summary": "No longer needed"},
            headers={**self.headers, "if-match": '"v0"'},
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.headers["etag"], '"v1"')
        self.assertEqual(revoked.json()["data"]["state"], "REVOKED")
        self.assertEqual(self.authorizations.revoke_command.expected_lock_version, 0)

    def test_strict_payload_validation(self) -> None:
        for change, status in (
            ({"api_key": "forbidden"}, 400),
            ({"payload_fingerprint": "AA" * 32}, 422),
            ({"source_refs": []}, 422),
            ({"allowed_data_categories": ["X", "X"]}, 422),
            ({"max_payload_bytes": True}, 422),
        ):
            with self.subTest(change=change):
                result = self.client.post(
                    self.preview_path, json={**self.preview_body, **change}, headers=self.headers,
                )
                self.assertEqual(result.status_code, status)
        duplicate = '{"purpose_ref":"A","purpose_ref":"B"}'
        self.assertEqual(self.client.post(
            self.preview_path, content=duplicate,
            headers={**self.headers, "content-type": "application/json"},
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.preview_path + "?unexpected=1", json=self.preview_body,
            headers=self.headers,
        ).status_code, 400)
        authorize_path = self.preview_path + "/" + str(self.preview_id) + ":authorize"
        self.assertEqual(self.client.post(
            authorize_path, json={**self.authorize_body, "valid_until": "2026-10-03T12:25:06+08:00"},
            headers={**self.headers, "if-match": '"v0"'},
        ).status_code, 422)

    def test_security_preconditions(self) -> None:
        authorize_path = self.preview_path + "/" + str(self.preview_id) + ":authorize"
        self.assertEqual(self.client.post(
            authorize_path, json=self.authorize_body, headers=self.headers,
        ).status_code, 428)
        self.assertEqual(self.client.post(
            authorize_path, json=self.authorize_body,
            headers={**self.headers, "if-match": 'W/"v0"'},
        ).status_code, 400)
        self.assertEqual(self.client.post(
            authorize_path, json=self.authorize_body,
            headers={**self.headers, "if-match": '"v1"'},
        ).status_code, 409)
        self.assertEqual(self.client.post(
            self.preview_path, json=self.preview_body,
            headers={**self.headers, "origin": "https://evil.test"},
        ).status_code, 403)
        self.assertEqual(self.client.post(
            self.preview_path, json=self.preview_body,
            headers={**self.headers, "cookie": "plm_session=short"},
        ).status_code, 401)
        self.sessions.valid = False
        self.assertEqual(self.client.get(
            self.preview_path + "/" + str(self.preview_id),
            headers={"cookie": self.headers["cookie"]},
        ).status_code, 401)

    def test_safe_error_mapping(self) -> None:
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("CONFLICT_IDEMPOTENCY", 409),
            ("AI_EGRESS_POLICY_DENIED", 422), ("AI_EGRESS_ROUTE_UNAVAILABLE", 503),
            ("AI_EGRESS_PREVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.previews.failure = code
                response = self.client.post(
                    self.preview_path, json=self.preview_body, headers=self.headers,
                )
                self.assertEqual(response.status_code, status)
        self.previews.failure = None
        authorize_path = self.preview_path + "/" + str(self.preview_id) + ":authorize"
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("CONFLICT_VERSION", 409),
            ("CONFLICT_IDEMPOTENCY", 409), ("AI_EGRESS_APPROVAL_DENIED", 422),
            ("AI_EGRESS_AUTHORIZATION_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.authorizations.failure = code
                response = self.client.post(
                    authorize_path, json=self.authorize_body,
                    headers={**self.headers, "if-match": '"v0"'},
                )
                self.assertEqual(response.status_code, status)


if __name__ == "__main__":
    unittest.main()
