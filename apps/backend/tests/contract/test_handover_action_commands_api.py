from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.handover.api.action_commands import (
    create_handover_action_command_router,
)
from plm_assistant.modules.handover.application.create_action import (
    HandoverActionCreateError,
    HandoverActionInitialView,
)
from plm_assistant.modules.handover.application.patch_action import (
    HandoverActionPatchError,
    HandoverActionPatchView,
)


NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
PROJECT = uuid.uuid4()
ACTION = uuid.uuid4()
VERSION = uuid.uuid4()
ITEM = uuid.uuid4()
OWNER = uuid.uuid4()
CREATOR = uuid.uuid4()
EVENT = uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Creates:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise HandoverActionCreateError(self.fail)
        return HandoverActionInitialView(
            ACTION, PROJECT, "ANALYSIS_ITEM", VERSION, ITEM, None,
            command.action_type, command.title, command.requested_input_spec,
            command.owner_ref, command.due_at, command.priority, CREATOR,
            command.created_reason, NOW, EVENT,
        )


class Patches:
    def __init__(self):
        self.last = None
        self.fail = None

    def patch(self, command):
        self.last = command
        if self.fail:
            raise HandoverActionPatchError(self.fail)
        return HandoverActionPatchView(
            ACTION, PROJECT, command.title or "Confirm scope",
            command.requested_input_spec or {"fields": []},
            command.owner_ref or OWNER, command.due_at or NOW + timedelta(days=7),
            command.priority or "HIGH", "OPEN", NOW, '"v1"',
        )


class HandoverActionCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.creates, self.patches = Creates(), Patches()
        router = create_handover_action_command_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates, patches=self.patches,
        )
        self.client = TestClient(
            create_app(handover_action_command_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/handover-action-items"
        self.path = f"{self.root}/{ACTION}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }
        self.spec = {"fields": [{
            "name": "scope", "format": "text",
            "example": "Business A", "required": True,
        }]}
        self.body = {
            "source_analysis_version_ref": str(VERSION),
            "source_item_id": str(ITEM), "human_source_reason": None,
            "action_type": "CONFIRM_DECISION", "title": "Confirm scope",
            "requested_input_spec": self.spec, "owner_ref": str(OWNER),
            "due_at": "2026-10-12T12:00:00Z", "priority": "HIGH",
            "created_reason": "Project manager registered confirmation",
        }

    def test_default_closed_and_create_patch_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.root).status_code)
            self.assertEqual(404, bare.patch(self.path).status_code)

        created = self.client.post(self.root, headers=self.headers, json=self.body)
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual(self.path, created.headers["location"])
        self.assertEqual("OPEN", created.json()["data"]["action_state"])
        self.assertEqual(VERSION, self.creates.last.source_analysis_version_ref)

        patched = self.client.patch(
            self.path, headers=self.headers,
            json={"title": "Confirm final scope", "priority": "URGENT"},
        )
        self.assertEqual(200, patched.status_code)
        self.assertEqual('"v1"', patched.headers["etag"])
        self.assertEqual(0, self.patches.last.expected_version)
        self.assertEqual("URGENT", self.patches.last.priority)
        self.assertIsNone(self.patches.last.owner_ref)

    def test_security_shape_and_canonical_values_fail_closed(self):
        evil = {**self.headers, "origin": "https://evil.test"}
        self.assertEqual(403, self.client.post(
            self.root, headers=evil, json=self.body,
        ).status_code)
        no_key = {key: value for key, value in self.headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.root, headers=no_key, json=self.body,
        ).status_code)
        no_match = {key: value for key, value in self.headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.patch(
            self.path, headers=no_match, json={"priority": "HIGH"},
        ).status_code)
        self.assertEqual(400, self.client.patch(
            self.path, headers=self.headers, json={},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root, headers=self.headers, json={**self.body, "unknown": True},
        ).status_code)
        self.assertEqual(422, self.client.post(
            self.root, headers=self.headers,
            json={**self.body, "due_at": "2026-10-12T20:00:00+08:00"},
        ).status_code)
        upper = f"/api/v1/projects/{str(PROJECT).upper()}/handover-action-items"
        self.assertEqual(422, self.client.post(
            upper, headers=self.headers, json=self.body,
        ).status_code)

    def test_owner_errors_have_stable_safe_mapping(self):
        self.creates.fail = "AUTH_ACCESS_DENIED"
        response = self.client.post(self.root, headers=self.headers, json=self.body)
        self.assertEqual(404, response.status_code)
        self.assertEqual("RESOURCE_NOT_FOUND", response.json()["error"]["code"])

        self.patches.fail = "HANDOVER_STATE_INVALID"
        response = self.client.patch(
            self.path, headers=self.headers, json={"priority": "LOW"},
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual(
            "HANDOVER_ACTION_STATE_INVALID", response.json()["error"]["code"],
        )


if __name__ == "__main__":
    unittest.main()
