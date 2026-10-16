from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.workflow.api.transition_stage import (
    create_workflow_stage_transition_router,
)
from plm_assistant.modules.workflow.application.append_stage_transition import (
    PersistedStageTransition, PersistedTransitionGate,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation,
)
from plm_assistant.modules.workflow.application.transition_stage import (
    WorkflowStageTransitionError,
)
from plm_assistant.modules.workflow.domain.history import (
    ForwardTransitionSnapshot, GateItemSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT, WORKFLOW, TRANSITION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
ACTOR, TRACE = uuid.uuid4(), uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if (token != b"s" * 32 or csrf_token != b"c" * 32
                or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def view() -> PersistedStageTransition:
    gates = []
    snapshots = []
    for index, item_key in enumerate((
            "HANDOVER_BASELINE", "HANDOVER_ISSUES")):
        evidence, review = uuid.uuid4(), uuid.uuid4()
        basis = tuple(sorted((
            ChecklistBasisObservation(
                "EVIDENCE", evidence, "PROJECT", PROJECT, "ELIGIBLE",
                2, bytes([index + 1]) * 32, NOW, 1,
            ),
            ChecklistBasisObservation(
                "REVIEW_ROUND", review, "PROJECT", PROJECT, "APPROVED",
                3, bytes([index + 10]) * 32, NOW, 1,
            ),
        ), key=lambda item: (item.ref_kind, str(item.ref_id))))
        snapshot = GateItemSnapshot(
            item_key, ChecklistState.PASS, (evidence,), (review,),
        )
        snapshots.append(snapshot)
        gates.append(PersistedTransitionGate(
            uuid.uuid4(), uuid.uuid4(), 1,
            bytes([index + 20]) * 32, snapshot, basis,
        ))
    snapshot = ForwardTransitionSnapshot(
        WORKFLOW, PROJECT, ACTOR, TRACE, 1,
        "HANDOVER", "SURVEY", 3, 4,
        "Handover accepted", NOW, tuple(snapshots),
    )
    return PersistedStageTransition(
        TRANSITION, snapshot, tuple(gates), b"t" * 32, 4,
    )


class Transitions:
    def __init__(self):
        self.calls = []
        self.result = view()

    def transition(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class WorkflowStageTransitionApiTests(unittest.TestCase):
    def setUp(self):
        self.transitions = Transitions()
        router = create_workflow_stage_transition_router(
            sessions=Sessions(), transitions=self.transitions,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(
            create_app(workflow_transition_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{PROJECT}/workflow:transition"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "workflow-transition-http-001",
            "if-match": '"v3"',
        }
        self.body = {
            "target_stage_key": "SURVEY",
            "reason": "Handover accepted",
            "gate_snapshot_refs": [],
        }

    def test_default_closed_and_exact_success_projection(self):
        with TestClient(
            create_app(), base_url="https://plm.example.test",
        ) as bare:
            self.assertEqual(404, bare.post(self.path).status_code)
        response = self.client.post(
            self.path, headers=self.headers, json=self.body,
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual('"v4"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        data = response.json()["data"]
        self.assertEqual({
            "stage_transition_id", "workflow_id", "project_id",
            "definition_version", "from_stage", "to_stage",
            "before_workflow_version", "transitioned_workflow_version",
            "current_workflow_version", "reason", "occurred_at", "etag",
        }, set(data))
        self.assertEqual(str(TRANSITION), data["stage_transition_id"])
        self.assertEqual("HANDOVER", data["from_stage"])
        self.assertEqual("SURVEY", data["to_stage"])
        self.assertEqual("2026-10-06T00:00:00Z", data["occurred_at"])
        command, key = self.transitions.calls[0]
        self.assertEqual(PROJECT, command.project_id)
        self.assertEqual(3, command.expected_workflow_version)
        self.assertEqual("workflow-transition-http-001", key)
        self.assertEqual(str(command.trace_id), response.json()["trace_id"])

    def test_security_and_exact_reserved_snapshot_shape(self):
        variants = (
            ({key: value for key, value in self.headers.items()
              if key != "cookie"}, self.path, self.body, None, 401),
            ({key: value for key, value in self.headers.items()
              if key != "x-csrf-token"}, self.path, self.body, None, 403),
            (self.headers | {"origin": "https://evil.test"}, self.path,
             self.body, None, 403),
            ({key: value for key, value in self.headers.items()
              if key != "idempotency-key"}, self.path, self.body, None, 422),
            ({key: value for key, value in self.headers.items()
              if key != "if-match"}, self.path, self.body, None, 428),
            (self.headers | {"if-match": 'W/"v3"'}, self.path,
             self.body, None, 400),
            (self.headers, self.path + "?extra=1", self.body, None, 400),
            (self.headers, self.path, self.body | {"unknown": True}, None, 400),
            (self.headers, self.path,
             {"target_stage_key": "SURVEY", "reason": "ok"}, None, 400),
            (self.headers, self.path,
             self.body | {"gate_snapshot_refs": [str(uuid.uuid4())]},
             None, 422),
            (self.headers, self.path,
             self.body | {"gate_snapshot_refs": {}}, None, 422),
            (self.headers, self.path,
             self.body | {"target_stage_key": 1}, None, 422),
            (self.headers,
             self.path.replace(str(PROJECT), str(PROJECT).upper()),
             self.body, None, 422),
            (self.headers | {"content-type": "application/json"},
             self.path, None,
             b'{"target_stage_key":"SURVEY",'
             b'"target_stage_key":"PLAN","reason":"ok",'
             b'"gate_snapshot_refs":[]}', 400),
        )
        for headers, path, body, content, status in variants:
            with self.subTest(status=status, path=path):
                response = self.client.post(
                    path, headers=headers,
                    json=body if content is None else None,
                    content=content,
                )
                self.assertEqual(status, response.status_code, response.text)
        self.assertEqual([], self.transitions.calls)

    def test_service_errors_have_safe_frozen_mapping(self):
        for error, code, status in (
            (WorkflowStageTransitionError("AUTH_ACCESS_DENIED"),
             "AUTH_SESSION_EXPIRED", 401),
            (WorkflowStageTransitionError("RESOURCE_NOT_FOUND"),
             "RESOURCE_NOT_FOUND", 404),
            (WorkflowStageTransitionError("WORKFLOW_GATE_NOT_SATISFIED"),
             "WORKFLOW_GATE_NOT_SATISFIED", 409),
            (WorkflowStageTransitionError("WORKFLOW_TRANSITION_INVALID"),
             "WORKFLOW_TRANSITION_INVALID", 409),
            (WorkflowStageTransitionError("CONFLICT_VERSION"),
             "CONFLICT_VERSION", 409),
            (WorkflowStageTransitionError("CONFLICT_IDEMPOTENCY"),
             "CONFLICT_IDEMPOTENCY", 409),
            (RuntimeError("private transition data"),
             "SYSTEM_UNAVAILABLE", 503),
        ):
            self.transitions.result = error
            with self.subTest(code=code):
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body,
                )
                self.assertEqual(status, response.status_code)
                self.assertEqual(code, response.json()["error"]["code"])
                self.assertNotIn("private transition data", response.text)

    def test_foreign_or_inconsistent_result_is_rejected(self):
        original = view()
        foreign = uuid.uuid4()
        for candidate in (
            replace(original, snapshot=replace(
                original.snapshot, project_id=foreign,
            )),
            replace(original, snapshot=replace(
                original.snapshot, before_lock_version=2,
                after_lock_version=3,
            )),
        ):
            self.transitions.result = candidate
            with self.subTest(candidate=candidate):
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body,
                )
                self.assertEqual(503, response.status_code)


if __name__ == "__main__":
    unittest.main()
