from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.workflow.api.record_checklist import (
    create_workflow_checklist_record_router,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation, CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.application.record_checklist import (
    WorkflowChecklistRecordError,
)
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT = uuid.uuid4()
WORKFLOW = uuid.uuid4()
RECORD = uuid.uuid4()
ACTOR = uuid.uuid4()
TRACE = uuid.uuid4()
EVIDENCE = uuid.uuid4()
ROUND = uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def view() -> CurrentChecklistRecord:
    record = ChecklistRecordSnapshot(
        RECORD, WORKFLOW, PROJECT, ACTOR, TRACE, 1, "HANDOVER",
        "HANDOVER_BASELINE", ChecklistState.PENDING, ChecklistState.PASS,
        0, 1, 4, 5, NOW, None, (EVIDENCE,), (ROUND,), (),
        "Approved baseline", "Handover may proceed",
    )
    basis = (
        ChecklistBasisObservation(
            "EVIDENCE", EVIDENCE, "PROJECT", PROJECT, "ELIGIBLE", 2,
            b"e" * 32, NOW, 1,
        ),
        ChecklistBasisObservation(
            "REVIEW_ROUND", ROUND, "PROJECT", PROJECT, "APPROVED", 3,
            b"r" * 32, NOW, 1,
        ),
    )
    return CurrentChecklistRecord(record, basis, b"f" * 32, "ACTIVE", 5)


class Records:
    def __init__(self):
        self.calls = []
        self.result = view()

    def record(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class WorkflowChecklistRecordApiTests(unittest.TestCase):
    def setUp(self):
        self.records = Records()
        router = create_workflow_checklist_record_router(
            sessions=Sessions(), records=self.records,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(
            create_app(workflow_checklist_record_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = (
            f"/api/v1/projects/{PROJECT}/workflow/checklist-items/"
            "HANDOVER_BASELINE:record"
        )
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "workflow-checklist-record-01",
            "if-match": '"v4"',
        }
        self.body = {
            "result": "PASS", "reason": "Approved baseline",
            "impact": "Handover may proceed",
            "evidence_refs": [str(EVIDENCE)], "exception_refs": [],
        }

    def test_default_closed_and_exact_success_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.path).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v5"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        data = response.json()["data"]
        self.assertEqual({
            "record_id", "workflow_id", "project_id", "definition_version",
            "stage_key", "item_key", "result", "item_version",
            "recorded_workflow_version", "current_workflow_version",
            "supersedes_record_id", "evidence_refs", "review_round_refs",
            "exception_refs", "reason", "impact", "occurred_at", "etag",
        }, set(data))
        self.assertEqual("PASS", data["result"])
        self.assertEqual([str(ROUND)], data["review_round_refs"])
        self.assertEqual("2026-10-06T00:00:00Z", data["occurred_at"])
        command, key = self.records.calls[0]
        self.assertEqual(PROJECT, command.project_id)
        self.assertEqual(4, command.expected_workflow_version)
        self.assertEqual((EVIDENCE,), command.evidence_refs)
        self.assertEqual("workflow-checklist-record-01", key)
        self.assertEqual(str(command.trace_id), response.json()["trace_id"])

    def test_security_and_request_shape_reject_before_service(self):
        variants = (
            ({key: value for key, value in self.headers.items() if key != "cookie"},
             self.path, self.body, None, 401),
            ({key: value for key, value in self.headers.items()
              if key != "x-csrf-token"}, self.path, self.body, None, 403),
            (self.headers | {"origin": "https://evil.test"}, self.path,
             self.body, None, 403),
            ({key: value for key, value in self.headers.items()
              if key != "idempotency-key"}, self.path, self.body, None, 422),
            ({key: value for key, value in self.headers.items()
              if key != "if-match"}, self.path, self.body, None, 428),
            (self.headers | {"if-match": 'W/"v4"'}, self.path,
             self.body, None, 400),
            (self.headers, self.path + "?extra=1", self.body, None, 400),
            (self.headers, self.path, self.body | {"unknown": True}, None, 400),
            (self.headers, self.path, {"result": "PASS"}, None, 400),
            (self.headers, self.path, self.body | {"result": "PENDING"}, None, 422),
            (self.headers, self.path,
             self.body | {"evidence_refs": [str(EVIDENCE).upper()]}, None, 422),
            (self.headers,
             self.path.replace(str(PROJECT), str(PROJECT).upper()),
             self.body, None, 422),
            (self.headers, self.path, None,
             b'{"result":"PASS","result":"FAIL",'
             b'"evidence_refs":[],"exception_refs":[]}', 400),
        )
        for headers, path, body, content, status in variants:
            with self.subTest(status=status, path=path):
                response = self.client.post(
                    path, headers=headers,
                    json=body if content is None else None,
                    content=content,
                )
                self.assertEqual(status, response.status_code, response.text)
        self.assertEqual([], self.records.calls)

    def test_fail_shape_reaches_service_without_fabricated_refs(self):
        failed = replace(
            view().record, result=ChecklistState.FAIL,
            evidence_refs=(), review_round_refs=(), reason="Missing approval",
        )
        self.records.result = CurrentChecklistRecord(
            failed, (), b"x" * 32, "ACTIVE", 5,
        )
        body = {
            "result": "FAIL", "reason": "Missing approval",
            "evidence_refs": [], "exception_refs": [],
        }
        response = self.client.post(self.path, headers=self.headers, json=body)
        self.assertEqual(200, response.status_code)
        self.assertEqual((), self.records.calls[0][0].evidence_refs)

    def test_service_errors_have_stable_safe_mapping(self):
        for error, code, status in (
            (WorkflowChecklistRecordError("AUTH_ACCESS_DENIED"),
             "AUTH_SESSION_EXPIRED", 401),
            (WorkflowChecklistRecordError("RESOURCE_NOT_FOUND"),
             "RESOURCE_NOT_FOUND", 404),
            (WorkflowChecklistRecordError("WORKFLOW_GATE_NOT_SATISFIED"),
             "WORKFLOW_GATE_NOT_SATISFIED", 409),
            (WorkflowChecklistRecordError("CONFLICT_VERSION"),
             "CONFLICT_VERSION", 409),
            (WorkflowChecklistRecordError("CONFLICT_IDEMPOTENCY"),
             "CONFLICT_IDEMPOTENCY", 409),
            (RuntimeError("private workflow data"), "SYSTEM_UNAVAILABLE", 503),
        ):
            self.records.result = error
            with self.subTest(code=code):
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body,
                )
                self.assertEqual(status, response.status_code)
                self.assertEqual(code, response.json()["error"]["code"])
                self.assertNotIn("private workflow data", response.text)

    def test_foreign_or_inconsistent_result_is_rejected(self):
        original = view()
        foreign = uuid.uuid4()
        foreign_view = CurrentChecklistRecord(
            replace(original.record, project_id=foreign),
            tuple(replace(value, ref_project_id=foreign)
                  for value in original.basis),
            original.content_fingerprint, original.observed_stage_state,
            original.current_workflow_version,
        )
        for candidate in (
            foreign_view,
            replace(original, record=replace(
                original.record, item_key="HANDOVER_ISSUES",
            )),
        ):
            self.records.result = candidate
            with self.subTest(candidate=candidate):
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body,
                )
                self.assertEqual(503, response.status_code)


if __name__ == "__main__":
    unittest.main()
