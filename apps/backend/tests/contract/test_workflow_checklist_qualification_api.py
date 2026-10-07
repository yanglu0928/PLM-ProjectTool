from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.workflow.api.qualification_preview import (
    create_workflow_checklist_qualification_router,
)
from plm_assistant.modules.workflow.application.preview_checklist_qualification import (
    WorkflowChecklistQualificationPreview,
    WorkflowChecklistQualificationPreviewError,
)


PROJECT = uuid.uuid4()
WORKFLOW = uuid.uuid4()
VERSION = uuid.uuid4()
ROUND = uuid.uuid4()
EVIDENCE = (uuid.uuid4(), uuid.uuid4())
TRACE = uuid.uuid4()


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Previews:
    def __init__(self):
        self.calls = []
        self.result = WorkflowChecklistQualificationPreview(
            WORKFLOW, PROJECT, 1, "HANDOVER", "HANDOVER_BASELINE",
            "PENDING", 4, VERSION, ROUND, EVIDENCE,
        )

    def get(self, query):
        self.calls.append(query)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class WorkflowChecklistQualificationApiTests(unittest.TestCase):
    def setUp(self):
        self.previews = Previews()
        router = create_workflow_checklist_qualification_router(
            sessions=Sessions(), previews=self.previews,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(
            create_app(workflow_checklist_qualification_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = (
            f"/api/v1/projects/{PROJECT}/workflow/checklist-items/"
            "HANDOVER_BASELINE/qualification"
        )
        self.headers = {
            "host": "plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
        }

    def test_default_closed_and_exact_minimal_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v4"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        payload = response.json()
        self.assertEqual(str(self.previews.calls[0].trace_id),
                         payload["trace_id"])
        data = payload["data"]
        self.assertEqual({
            "workflow_id", "project_id", "definition_version",
            "stage_key", "item_key", "current_item_state",
            "workflow_etag", "handover_analysis_version_id",
            "review_round_ref", "evidence_refs",
        }, set(data))
        self.assertEqual(str(PROJECT), data["project_id"])
        self.assertEqual([str(value) for value in EVIDENCE],
                         data["evidence_refs"])
        self.assertNotIn("content_fingerprint", response.text)
        self.assertNotIn("document", response.text.lower())

    def test_security_shape_and_canonical_path_reject_before_service(self):
        variants = (
            ({"host": "plm.example.test"}, self.path, 401),
            (self.headers | {"host": "evil.example.test"}, self.path, 403),
            (self.headers, self.path + "?extra=1", 400),
            (self.headers, self.path.replace(str(PROJECT), str(PROJECT).upper()), 422),
            (self.headers, self.path.replace(
                "HANDOVER_BASELINE", "REQUIREMENT_ACCEPTANCE"), 422),
        )
        for headers, path, status in variants:
            with self.subTest(status=status, path=path):
                response = self.client.get(path, headers=headers)
                self.assertEqual(status, response.status_code, response.text)
        self.assertEqual([], self.previews.calls)

    def test_survey_projection_uses_strict_subject_variant(self):
        self.previews.result = WorkflowChecklistQualificationPreview(
            WORKFLOW, PROJECT, 1, "SURVEY", "SURVEY_CONCLUSION",
            "PENDING", 5, None, ROUND, EVIDENCE, VERSION,
        )
        path = self.path.replace("HANDOVER_BASELINE", "SURVEY_CONCLUSION")
        response = self.client.get(path, headers=self.headers)
        self.assertEqual(200, response.status_code, response.text)
        data = response.json()["data"]
        self.assertEqual("SURVEY", data["stage_key"])
        self.assertEqual(str(VERSION), data["survey_conclusion_id"])
        self.assertNotIn("handover_analysis_version_id", data)

    def test_safe_service_errors_have_stable_statuses(self):
        for code, status, public in (
            ("AUTH_ACCESS_DENIED", 401, "AUTH_SESSION_EXPIRED"),
            ("RESOURCE_NOT_FOUND", 404, "RESOURCE_NOT_FOUND"),
            ("PROJECT_ARCHIVED", 409, "PROJECT_ARCHIVED"),
            ("CONFLICT_STATE", 409, "CONFLICT_STATE"),
            ("CONFLICT_VERSION", 409, "CONFLICT_VERSION"),
            ("WORKFLOW_GATE_NOT_SATISFIED", 409,
             "WORKFLOW_GATE_NOT_SATISFIED"),
            ("LICENSE_OPERATION_DENIED", 403,
             "LICENSE_OPERATION_DENIED"),
            ("WORKFLOW_UNAVAILABLE", 503, "SYSTEM_UNAVAILABLE"),
        ):
            self.previews.result = (
                WorkflowChecklistQualificationPreviewError(code)
            )
            with self.subTest(code=code):
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(status, response.status_code, response.text)
                self.assertEqual(public, response.json()["error"]["code"])

    def test_foreign_or_malformed_projection_is_system_failure(self):
        for candidate in (
            WorkflowChecklistQualificationPreview(
                WORKFLOW, uuid.uuid4(), 1, "HANDOVER",
                "HANDOVER_BASELINE", "PENDING", 4,
                VERSION, ROUND, EVIDENCE,
            ),
            object(),
        ):
            self.previews.result = candidate
            with self.subTest(candidate=candidate):
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(503, response.status_code)


if __name__ == "__main__":
    unittest.main()
