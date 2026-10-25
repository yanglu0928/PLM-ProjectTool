from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.prototype.api.cursors import PrototypeCursorCodec
from plm_assistant.modules.prototype.api.prototypes import create_prototype_router
from plm_assistant.modules.prototype.application.create_identity import PrototypeInitialView
from plm_assistant.modules.prototype.application.mark_not_required import PrototypeScopeDecisionView
from plm_assistant.modules.prototype.application.mutate_prototype import PrototypeIdentityView
from plm_assistant.modules.prototype.application.read_identities import PrototypePage, PrototypeSummary


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, PROTOTYPE, ACTOR, REQUIREMENT = (uuid.uuid4() for _ in range(4))
SUMMARY = PrototypeSummary(PROTOTYPE, PROJECT, "Portal", "ACTIVE", None,
    ACTOR, NOW, None, NOW, '"v0"')


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32 or require_csrf and csrf_token != b"c" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    def list_prototypes(self, query, *, page_size, after_updated_at=None, after_prototype_id=None):
        self.after = (after_updated_at, after_prototype_id)
        more = after_updated_at is None
        return PrototypePage((SUMMARY,), NOW if more else None, PROTOTYPE if more else None, more)
    def get_prototype(self, query, prototype_id): return SUMMARY


class Creates:
    def create_prototype(self, command):
        self.command = command
        return PrototypeInitialView(PROTOTYPE, PROJECT, command.name, NOW)


class Mutations:
    def patch(self, command):
        self.command = command
        return PrototypeIdentityView(PROTOTYPE, PROJECT, command.name, "ACTIVE", None, '"v1"')
    def archive(self, command):
        self.command = command
        return PrototypeIdentityView(PROTOTYPE, PROJECT, "Portal", "ARCHIVED", None, '"v1"')


class Decisions:
    def mark_not_required(self, command):
        self.command = command
        return PrototypeScopeDecisionView(PROTOTYPE, PROJECT, "Portal", "NOT_REQUIRED",
            uuid.uuid4(), command.reason, command.impact, ACTOR, None, None,
            tuple(sorted(command.affected_requirement_version_refs, key=str)), NOW, '"v1"')


class PrototypeApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates, self.mutations, self.decisions = Reads(), Creates(), Mutations(), Decisions()
        router = create_prototype_router(sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]), reads=self.reads,
            creates=self.creates, mutations=self.mutations, decisions=self.decisions,
            cursors=PrototypeCursorCodec(b"q" * 32))
        self.client = TestClient(create_app(prototype_router=router), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/prototypes"
        self.detail = f"{self.root}/{PROTOTYPE}"
        self.read = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write = {**self.read, "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(), "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"'}

    def test_default_closed_and_six_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for method, path in (("get", self.root), ("post", self.root), ("get", self.detail),
                    ("patch", self.detail), ("post", self.detail + ":mark-not-required"),
                    ("post", self.detail + ":archive")):
                self.assertEqual(404, getattr(bare, method)(path).status_code)
        first = self.client.get(self.root + "?page_size=1", headers=self.read)
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(200, self.client.get(self.root + f"?page_size=1&cursor={cursor}", headers=self.read).status_code)
        self.assertEqual(201, self.client.post(self.root, headers=self.write, json={"name": "Portal"}).status_code)
        self.assertEqual(200, self.client.get(self.detail, headers=self.read).status_code)
        patch_headers = {k: v for k, v in self.write.items() if k != "idempotency-key"}
        self.assertEqual(200, self.client.patch(self.detail, headers=patch_headers, json={"name": "Portal 2"}).status_code)
        marked = self.client.post(self.detail + ":mark-not-required", headers=self.write,
            json={"affected_requirement_version_refs": [str(REQUIREMENT)],
                  "reason": "No custom interaction", "impact": "Use standard form"})
        self.assertEqual(200, marked.status_code)
        self.assertEqual("NOT_REQUIRED", marked.json()["data"]["state"])
        archived = self.client.post(self.detail + ":archive", headers=self.write, content=b"")
        self.assertEqual(200, archived.status_code)
        self.assertEqual("ARCHIVED", archived.json()["data"]["state"])

    def test_security_preconditions_scope_and_strict_body(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.post(self.root,
            headers={**self.write, "origin": "https://evil.test"}, json={"name": "x"}).status_code)
        no_match = {k: v for k, v in self.write.items() if k != "if-match"}
        self.assertEqual(428, self.client.patch(self.detail, headers=no_match, json={"name": "x"}).status_code)
        no_key = {k: v for k, v in self.write.items() if k != "idempotency-key"}
        self.assertEqual(422, self.client.post(self.detail + ":archive", headers=no_key, content=b"").status_code)
        self.assertEqual(400, self.client.get(self.root + "?page_size=1&page_size=1", headers=self.read).status_code)
        self.assertEqual(400, self.client.post(self.detail + ":mark-not-required", headers=self.write,
            json={"affected_requirement_version_refs": [str(REQUIREMENT)], "reason": "r",
                  "impact": "i", "review_id": str(uuid.uuid4())}).status_code)
        first = self.client.get(self.root + "?page_size=1", headers=self.read)
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            f"/api/v1/projects/{uuid.uuid4()}/prototypes?page_size=1&cursor={cursor}",
            headers=self.read).status_code)


if __name__ == "__main__": unittest.main()
