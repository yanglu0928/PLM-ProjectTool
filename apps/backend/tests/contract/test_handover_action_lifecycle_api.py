from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.handover.api.action_commands import (
    create_handover_action_lifecycle_router,
)
from plm_assistant.modules.handover.application.cancel_action import (
    HandoverActionCancelError, HandoverActionCancelView,
)
from plm_assistant.modules.handover.application.close_action import HandoverActionCloseView
from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.handover.application.start_action import HandoverActionStartView
from plm_assistant.modules.handover.application.submit_action import HandoverActionSubmitView
from plm_assistant.modules.handover.application.verify_action import HandoverActionVerifyView


NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
PROJECT, ACTION, EVENT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
DOCUMENT, VERSION, EVIDENCE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
VERIFY_EVIDENCE, ACTOR, TRACE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Service:
    def __init__(self, method, factory):
        self.last = None
        self.fail = None
        self.method = method
        self.factory = factory
        setattr(self, method, self.call)

    def call(self, command):
        self.last = command
        if self.fail:
            raise HandoverActionCancelError(self.fail)
        return self.factory(command)


class HandoverActionLifecycleApiTests(unittest.TestCase):
    def setUp(self):
        self.start = Service("start", lambda command: HandoverActionStartView(
            ACTION, PROJECT, EVENT, "IN_PROGRESS", NOW, '"v1"',
        ))
        self.submit = Service("submit", lambda command: HandoverActionSubmitView(
            ACTION, PROJECT, EVENT, "SUBMITTED", NOW,
            command.response_documents, command.evidence_refs, '"v2"',
        ))
        self.verify = Service("verify", lambda command: HandoverActionVerifyView(
            ACTION, PROJECT, EVENT, "VERIFIED", ACTOR, NOW,
            command.evidence_refs, '"v3"',
        ))
        self.close = Service("close", lambda command: HandoverActionCloseView(
            ACTION, PROJECT, EVENT, "CLOSED", command.resolution_trace_ref,
            NOW, '"v4"',
        ))
        self.cancel = Service("cancel", lambda command: HandoverActionCancelView(
            ACTION, PROJECT, EVENT, "CANCELLED", "OPEN", command.reason,
            NOW, '"v1"',
        ))
        router = create_handover_action_lifecycle_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            starts=self.start, submits=self.submit, verifies=self.verify,
            closes=self.close, cancels=self.cancel,
        )
        self.client = TestClient(
            create_app(handover_action_lifecycle_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/handover-action-items/{ACTION}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
        }

    def test_default_closed_and_five_transition_contracts(self):
        suffixes = (":start", ":submit", ":verify", ":close", ":cancel")
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for suffix in suffixes:
                self.assertEqual(404, bare.post(self.root + suffix).status_code)

        started = self.client.post(
            self.root + ":start", headers=self.headers, json={"reason": "Work begun"},
        )
        self.assertEqual("IN_PROGRESS", started.json()["data"]["action_state"])
        submitted = self.client.post(self.root + ":submit", headers=self.headers, json={
            "response_documents": [{"document_id": str(DOCUMENT),
                                    "document_version_id": str(VERSION)}],
            "evidence_refs": [str(EVIDENCE)], "reason": "Response ready",
        })
        self.assertEqual("SUBMITTED", submitted.json()["data"]["action_state"])
        self.assertNotIn("closed_at", submitted.json()["data"])
        verified = self.client.post(self.root + ":verify", headers=self.headers, json={
            "evidence_refs": [str(VERIFY_EVIDENCE)], "reason": "Evidence checked",
        })
        self.assertEqual("VERIFIED", verified.json()["data"]["action_state"])
        closed = self.client.post(self.root + ":close", headers=self.headers, json={
            "resolution_trace_ref": str(TRACE), "reason": "Resolved downstream",
        })
        self.assertEqual("CLOSED", closed.json()["data"]["action_state"])
        cancelled = self.client.post(
            self.root + ":cancel", headers=self.headers,
            json={"reason": "No longer required"},
        )
        self.assertEqual("CANCELLED", cancelled.json()["data"]["action_state"])
        self.assertEqual([200] * 5, [
            started.status_code, submitted.status_code, verified.status_code,
            closed.status_code, cancelled.status_code,
        ])

    def test_all_transitions_require_security_concurrency_and_idempotency(self):
        no_match = {key: value for key, value in self.headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.post(
            self.root + ":start", headers=no_match, json={"reason": "Begin"},
        ).status_code)
        no_key = {key: value for key, value in self.headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.root + ":cancel", headers=no_key, json={"reason": "Stop"},
        ).status_code)
        self.assertEqual(403, self.client.post(
            self.root + ":start",
            headers={**self.headers, "origin": "https://evil.test"},
            json={"reason": "Begin"},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root + ":verify", headers=self.headers,
            json={"evidence_refs": [str(EVIDENCE)], "reason": "Checked", "extra": 1},
        ).status_code)
        self.assertEqual(422, self.client.post(
            self.root + ":close", headers=self.headers,
            json={"resolution_trace_ref": str(TRACE).upper(), "reason": "Closed"},
        ).status_code)

    def test_state_error_is_stable_and_safe(self):
        self.cancel.fail = "HANDOVER_ACTION_STATE_INVALID"
        result = self.client.post(
            self.root + ":cancel", headers=self.headers, json={"reason": "Stop"},
        )
        self.assertEqual(409, result.status_code)
        self.assertEqual("HANDOVER_ACTION_STATE_INVALID", result.json()["error"]["code"])


if __name__ == "__main__":
    unittest.main()
