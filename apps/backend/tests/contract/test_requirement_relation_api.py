from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.requirement.api.relation_cursor import RequirementRelationCursorCodec
from plm_assistant.modules.requirement.api.relations import create_requirement_relation_router
from plm_assistant.modules.requirement.application.relations import (
    RequirementRelationError, RequirementRelationPage,
    RequirementRelationView, RequirementVersionRef,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, LEFT_REQ, LEFT_VER, RIGHT_REQ, RIGHT_VER = (
    uuid.uuid4() for _ in range(5))
RELATION, REPLACEMENT, ACTOR = (uuid.uuid4() for _ in range(3))
LEFT = RequirementVersionRef(LEFT_REQ, LEFT_VER)
RIGHT = RequirementVersionRef(RIGHT_REQ, RIGHT_VER)


def view(relation_id=RELATION, state="ACTIVE", lock=0, superseded=None):
    return RequirementRelationView(
        relation_id, PROJECT, LEFT, RIGHT, "DEPENDS_ON", state, lock,
        ACTOR, NOW, superseded,
    )


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token != b"s" * 32
                or require_csrf and csrf_token != b"c" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Relations:
    fail = None
    malformed = False

    def _check(self, command):
        self.command = command
        if self.fail:
            raise RequirementRelationError(self.fail)

    def list(self, query, *, page_size, after_relation_id=None):
        self._check(query)
        self.after = after_relation_id
        item = view()
        if self.malformed:
            item = RequirementRelationView(
                RELATION, uuid.uuid4(), LEFT, RIGHT, "DEPENDS_ON",
                "ACTIVE", 0, ACTOR, NOW, None,
            )
        return RequirementRelationPage(
            (item,), RELATION if after_relation_id is None else None,
            after_relation_id is None,
        )

    def create(self, command):
        self._check(command)
        return view()

    def revoke(self, command):
        self._check(command)
        return view(state="REVOKED", lock=1)

    def supersede(self, command):
        self._check(command)
        return view(REPLACEMENT)


class RequirementRelationApiTests(unittest.TestCase):
    def setUp(self):
        self.relations = Relations()
        self.relations.fail, self.relations.malformed = None, False
        router = create_requirement_relation_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            relations=self.relations,
            cursors=RequirementRelationCursorCodec(b"r" * 32),
        )
        self.client = TestClient(create_app(
            requirement_relation_router=router,
        ), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/requirement-relations"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers, "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
        }
        self.body = {
            "source": {"requirement_id": str(LEFT_REQ),
                       "requirement_version_id": str(LEFT_VER)},
            "target": {"requirement_id": str(RIGHT_REQ),
                       "requirement_version_id": str(RIGHT_VER)},
            "relation_type": "DEPENDS_ON",
        }

    def test_default_closed_and_four_success_contracts(self):
        paths = (
            ("get", self.root), ("post", self.root),
            ("post", f"{self.root}/{RELATION}:revoke"),
            ("post", f"{self.root}/{RELATION}:supersede"),
        )
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for method, path in paths:
                self.assertEqual(404, getattr(bare, method)(path).status_code)
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers,
        )
        self.assertEqual(RELATION, self.relations.after)
        self.assertFalse(second.json()["data"]["has_more"])
        created = self.client.post(
            self.root, headers=self.write_headers, json=self.body,
        )
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        terminal_headers = {**self.write_headers, "if-match": '"v0"'}
        revoked = self.client.post(
            f"{self.root}/{RELATION}:revoke", headers=terminal_headers,
        )
        self.assertEqual(200, revoked.status_code)
        self.assertEqual('"v1"', revoked.headers["etag"])
        self.assertEqual(0, self.relations.command.expected_version)
        replaced = self.client.post(
            f"{self.root}/{RELATION}:supersede",
            headers=terminal_headers, json=self.body,
        )
        self.assertEqual(201, replaced.status_code)
        self.assertEqual(str(REPLACEMENT),
                         replaced.json()["data"]["requirement_relation_id"])

    def test_security_cursor_json_and_if_match_fail_closed(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.post(
            self.root, headers={**self.write_headers,
                                "origin": "https://evil.test"},
            json=self.body,
        ).status_code)
        self.assertEqual(428, self.client.post(
            f"{self.root}/{RELATION}:revoke", headers=self.write_headers,
        ).status_code)
        self.assertEqual(400, self.client.post(
            f"{self.root}/{RELATION}:revoke",
            headers={**self.write_headers, "if-match": '"v0"'}, json={},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root, headers=self.write_headers,
            json={**self.body, "extra": True},
        ).status_code)
        self.assertEqual(422, self.client.post(
            self.root, headers=self.write_headers,
            json={**self.body, "relation_type": "OTHER"},
        ).status_code)
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        cursor = first.json()["data"]["next_cursor"]
        other = f"/api/v1/projects/{uuid.uuid4()}/requirement-relations"
        self.assertEqual(400, self.client.get(
            other + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers,
        ).status_code)
        self.relations.malformed = True
        self.assertEqual(503, self.client.get(
            self.root, headers=self.read_headers,
        ).status_code)

    def test_safe_error_mapping(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("VALIDATION_FAILED", 422),
            ("REQUIREMENT_RELATION_CYCLE", 422),
            ("CONFLICT_IDEMPOTENCY", 409),
            ("PROJECT_ARCHIVED", 409),
            ("SYSTEM_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.relations.fail = code
                response = self.client.post(
                    self.root, headers=self.write_headers, json=self.body,
                )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
