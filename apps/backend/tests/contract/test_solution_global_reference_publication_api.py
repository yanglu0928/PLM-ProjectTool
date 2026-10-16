"""Opt-in GLOBAL candidate publication administrator HTTP contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.global_reference_publication import (
    create_global_reference_publication_router,
)
from plm_assistant.modules.solution.application.set_global_reference_publication import (
    GlobalReferencePublicationError, GlobalReferencePublicationResult,
)


ROOT, VERSION, EVENT = (uuid.uuid4() for _ in range(3))


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Publication:
    def __init__(self) -> None:
        self.commands = []
        self.error = None
        self.wrong_root = False

    def set(self, command):
        self.commands.append(command)
        if self.error:
            raise GlobalReferencePublicationError(self.error)
        return GlobalReferencePublicationResult(
            EVENT, uuid.uuid4() if self.wrong_root else command.reference_solution_id,
            command.expected_reference_version_id, command.expected_event_no + 1,
            command.event_kind, command.display_label, command.reason,
            datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc))


class GlobalReferencePublicationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.publication = Publication()
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "publication-" + "k" * 16,
        }
        self.path = (f"/api/v1/global/reference-solutions/"
                     f"{ROOT}:set-candidate-publication")
        self.body = {
            "reference_version_id": str(VERSION),
            "expected_event_no": 0,
            "event_kind": "PUBLISH",
            "display_label": "审定后的合成标签",
            "reason": "管理员确认无敏感来源",
        }
        router = create_global_reference_publication_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            publication=self.publication)
        self.client = TestClient(
            create_app(global_reference_publication_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_publish_revoke_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json=self.body).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual({
            "publication_event_id", "reference_solution_id", "reference_version_id",
            "event_no", "event_kind", "display_label", "reason", "created_at",
        }, set(data))
        self.assertEqual("审定后的合成标签", data["display_label"])
        self.assertEqual(1, data["event_no"])
        self.assertEqual("2026-10-09T08:00:00Z", data["created_at"])
        revoke = {**self.body, "expected_event_no": 1,
                  "event_kind": "REVOKE", "display_label": None}
        response = self.client.post(self.path, headers=self.headers, json=revoke)
        self.assertEqual(200, response.status_code, response.text)
        self.assertIsNone(response.json()["data"]["display_label"])
        self.assertEqual("REVOKE", self.publication.commands[-1].event_kind)

    def test_origin_session_headers_query_and_body_fail_closed(self) -> None:
        variants = (
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"},
             self.body, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"},
             self.body, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()},
             self.body, 403),
            (self.path, {k: v for k, v in self.headers.items()
                         if k != "idempotency-key"}, self.body, 422),
            (self.path + "?scope=PROJECT", self.headers, self.body, 400),
            (self.path, self.headers, {**self.body, "extra": True}, 400),
            (self.path, self.headers, {**self.body, "expected_event_no": True}, 422),
            (self.path, self.headers, {**self.body,
                                      "reference_version_id": str(uuid.uuid4()).upper()}, 422),
        )
        for path, headers, body, expected in variants:
            with self.subTest(expected=expected):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code, response.text)
        self.assertFalse(self.publication.commands)

    def test_owner_errors_and_projection_mismatch(self) -> None:
        for error, expected in (
            ("AUTH_ACCESS_DENIED", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("VERSION_CONFLICT", 409),
            ("CONFLICT_STATE", 409),
            ("SOURCE_UNAVAILABLE", 503),
        ):
            with self.subTest(error=error):
                self.publication.error = error
                response = self.client.post(self.path, headers=self.headers,
                                            json=self.body)
                self.assertEqual(expected, response.status_code, response.text)
        self.publication.error = None
        self.publication.wrong_root = True
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
