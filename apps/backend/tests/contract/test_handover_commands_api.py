from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.handover.api.commands import create_handover_command_router
from plm_assistant.modules.handover.application.change_analysis import HandoverAnalysisStateError
from plm_assistant.modules.handover.application.create_analysis import (
    HandoverAnalysisCreateError, HandoverAnalysisInitialView,
)
from plm_assistant.modules.handover.application.create_version import (
    CreatedHandoverVersion, HandoverVersionCreateError,
)
from plm_assistant.modules.handover.application.read_analyses import HandoverAnalysisView
from plm_assistant.modules.handover.application.validate_version import (
    HandoverVersionValidationError, HandoverVersionValidationReport,
)


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
PROJECT = uuid.uuid4()
ANALYSIS = uuid.uuid4()
VERSION = uuid.uuid4()
DOCUMENT = uuid.uuid4()
DOCUMENT_VERSION = uuid.uuid4()
BASELINE = uuid.uuid4()
BASELINE_VERSION = uuid.uuid4()
ITEM = uuid.uuid4()
CAPABILITY_ITEM = uuid.uuid4()
EVIDENCE = uuid.uuid4()
AI_TASK = uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Analyses:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise HandoverAnalysisCreateError(self.fail)
        return HandoverAnalysisInitialView(
            ANALYSIS, PROJECT, "Contract handover", "sha256:" + "a" * 64, NOW,
        )


def analysis_view(state="ACTIVE", etag='"v1"'):
    return HandoverAnalysisView(
        ANALYSIS, PROJECT, "Updated handover", "sha256:" + "a" * 64,
        state, None, uuid.uuid4(), NOW, NOW, etag,
    )


class States:
    def __init__(self):
        self.last = None
        self.fail = None

    def _check(self, command):
        self.last = command
        if self.fail:
            raise HandoverAnalysisStateError(self.fail)

    def patch(self, command):
        self._check(command)
        return analysis_view()

    def archive(self, command):
        self._check(command)
        return analysis_view("ARCHIVED", '"v2"')


class Versions:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise HandoverVersionCreateError(self.fail)
        return CreatedHandoverVersion(
            VERSION, ANALYSIS, PROJECT, 1, "DRAFT", "sha256:" + "a" * 64,
            BASELINE, BASELINE_VERSION, b"b" * 32, None, uuid.uuid4(), NOW, 0, 1,
        )


class Validations:
    def __init__(self):
        self.last = None
        self.fail = None

    def validate(self, command):
        self.last = command
        if self.fail:
            raise HandoverVersionValidationError(self.fail)
        return HandoverVersionValidationReport(
            uuid.uuid4(), command.trace_id, ANALYSIS, VERSION, PROJECT,
            1, "DRAFT", 1, 1, 1, 1, 1, True, (), NOW,
        )


class HandoverCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.analyses, self.states = Analyses(), States()
        self.versions, self.validations = Versions(), Validations()
        router = create_handover_command_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            analyses=self.analyses, states=self.states,
            versions=self.versions, validations=self.validations,
        )
        self.client = TestClient(
            create_app(handover_command_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/handover-analyses"
        self.analysis_path = f"{self.root}/{ANALYSIS}"
        self.version_path = f"{self.analysis_path}/versions/{VERSION}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }
        self.source = {
            "document_id": str(DOCUMENT),
            "document_version_id": str(DOCUMENT_VERSION),
        }
        self.analysis_body = {
            "analysis_purpose": "Contract handover",
            "source_documents": [self.source],
        }
        self.item = {
            "analysis_item_id": str(ITEM), "item_type": "GAP",
            "title": "Gap", "statement": "A verified difference",
            "impact": "Manual work", "severity": "MEDIUM", "priority": "HIGH",
            "recommendation": "Use the standard workflow",
            "confirmation_question": None, "required_input_spec": {},
            "source_missing": False, "evidence_refs": [str(EVIDENCE)],
            "capability_refs": [str(CAPABILITY_ITEM)], "options": [],
        }
        self.version_body = {
            "source_documents": [self.source],
            "capability_baseline_id": str(BASELINE),
            "capability_baseline_version_id": str(BASELINE_VERSION),
            "items": [self.item], "ai_task_refs": [str(AI_TASK)],
        }

    def test_default_closed_and_all_five_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.root).status_code)
            self.assertEqual(404, bare.patch(self.analysis_path).status_code)
            self.assertEqual(404, bare.post(self.analysis_path + ":archive").status_code)
            self.assertEqual(404, bare.post(self.analysis_path + "/versions").status_code)
            self.assertEqual(404, bare.post(self.version_path + ":validate").status_code)

        created = self.client.post(
            self.root, headers=self.headers, json=self.analysis_body,
        )
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual(self.analysis_path, created.headers["location"])
        self.assertEqual(PROJECT, self.analyses.last.project_id)

        patched = self.client.patch(
            self.analysis_path, headers=self.headers,
            json={"analysis_purpose": "Updated handover"},
        )
        self.assertEqual(200, patched.status_code)
        self.assertEqual('"v1"', patched.headers["etag"])
        self.assertEqual("Updated handover", self.states.last.analysis_purpose)

        archived = self.client.post(
            self.analysis_path + ":archive", headers=self.headers, content=b"",
        )
        self.assertEqual(200, archived.status_code)
        self.assertEqual("ARCHIVED", archived.json()["data"]["state"])

        version = self.client.post(
            self.analysis_path + "/versions", headers=self.headers,
            json=self.version_body,
        )
        self.assertEqual(201, version.status_code)
        self.assertEqual('"v1"', version.headers["etag"])
        self.assertEqual(self.version_path, version.headers["location"])
        self.assertEqual(CAPABILITY_ITEM,
                         self.versions.last.items[0].capability_refs[0].capability_item_id)

        validated = self.client.post(
            self.version_path + ":validate", headers=self.headers, content=b"",
        )
        self.assertEqual(200, validated.status_code)
        self.assertTrue(validated.json()["data"]["valid"])
        self.assertEqual([], validated.json()["data"]["blocking_issues"])

    def test_security_headers_query_and_json_are_fail_closed(self):
        self.assertEqual(403, self.client.post(
            self.root, headers={**self.headers, "origin": "https://evil.test"},
            json=self.analysis_body,
        ).status_code)
        no_key = {key: value for key, value in self.headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.root, headers=no_key, json=self.analysis_body,
        ).status_code)
        no_match = {key: value for key, value in self.headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.patch(
            self.analysis_path, headers=no_match, json={"analysis_purpose": "New"},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root + "?bad=1", headers=self.headers, json=self.analysis_body,
        ).status_code)
        duplicate = (
            b'{"analysis_purpose":"A","analysis_purpose":"B",'
            b'"source_documents":[]}'
        )
        self.assertEqual(400, self.client.post(self.root, headers={
            **self.headers, "content-type": "application/json",
        }, content=duplicate).status_code)
        upper_path = f"/api/v1/projects/{str(PROJECT).upper()}/handover-analyses"
        self.assertEqual(422, self.client.post(
            upper_path, headers=self.headers, json=self.analysis_body,
        ).status_code)
        malformed = {**self.version_body, "unexpected": True}
        self.assertEqual(400, self.client.post(
            self.analysis_path + "/versions", headers=self.headers, json=malformed,
        ).status_code)

    def test_error_mapping_is_stable_and_safe(self):
        self.analyses.fail = "AUTH_ACCESS_DENIED"
        response = self.client.post(
            self.root, headers=self.headers, json=self.analysis_body,
        )
        self.assertEqual(404, response.status_code)
        self.assertEqual("RESOURCE_NOT_FOUND", response.json()["error"]["code"])
        self.analyses.fail = None

        self.versions.fail = "HANDOVER_SOURCE_UNAVAILABLE"
        response = self.client.post(
            self.analysis_path + "/versions", headers=self.headers,
            json=self.version_body,
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual("HANDOVER_SOURCE_REQUIRED", response.json()["error"]["code"])
        self.versions.fail = "HANDOVER_EVIDENCE_UNAVAILABLE"
        response = self.client.post(
            self.analysis_path + "/versions", headers=self.headers,
            json=self.version_body,
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual("HANDOVER_ITEM_INCOMPLETE", response.json()["error"]["code"])
        self.versions.fail = None

        self.states.fail = "CONFLICT_VERSION"
        response = self.client.patch(
            self.analysis_path, headers=self.headers,
            json={"analysis_purpose": "New"},
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("CONFLICT_VERSION", response.json()["error"]["code"])
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
