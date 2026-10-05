from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.handover.api.read import create_handover_read_router
from plm_assistant.modules.handover.api.read_cursor import (
    HandoverAnalysisCursorCodec, HandoverItemCursorCodec,
    HandoverVersionCursorCodec,
)
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAITaskView, HandoverAnalysisItemPage, HandoverAnalysisItemView,
    HandoverAnalysisPage, HandoverAnalysisReadError,
    HandoverAnalysisVersionPage, HandoverAnalysisVersionView,
    HandoverAnalysisView, HandoverItemCapabilityView, HandoverItemOptionView,
    HandoverSourceDocumentView,
)


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
PROJECT, ANALYSIS, VERSION, ITEM, ACTOR = (uuid.uuid4() for _ in range(5))
DOCUMENT, DOCUMENT_VERSION, AI_TASK = (uuid.uuid4() for _ in range(3))
BASELINE, BASELINE_VERSION, CAPABILITY, EVIDENCE = (
    uuid.uuid4() for _ in range(4)
)

ANALYSIS_VIEW = HandoverAnalysisView(
    ANALYSIS, PROJECT, "Technical agreement review", "sha256:" + "a" * 64,
    "ACTIVE", None, ACTOR, NOW, NOW, '"v0"',
)
VERSION_VIEW = HandoverAnalysisVersionView(
    VERSION, ANALYSIS, PROJECT, 1, "DRAFT", "sha256:" + "a" * 64,
    BASELINE, BASELINE_VERSION, "b" * 64, 1, 1, 1, 1, 1,
    None, None, None, ACTOR, NOW,
    (HandoverSourceDocumentView(DOCUMENT, DOCUMENT_VERSION, 0),),
    (HandoverAITaskView(AI_TASK, 0),),
)
ITEM_VIEW = HandoverAnalysisItemView(
    ITEM, VERSION, ANALYSIS, PROJECT, 0, "NEED_CONFIRM", "Confirm scope",
    "Scope is not explicit", "Delivery may drift", "HIGH", "URGENT",
    "Confirm with project manager", "Which modules are in scope?",
    {"type": "object", "required": ["scope"]}, True, "CANDIDATE",
    (EVIDENCE,), (HandoverItemCapabilityView(
        BASELINE_VERSION, CAPABILITY, 0,
    ),), (HandoverItemOptionView("A", "Include", None, 0),),
)


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def _check(self, query):
        self.query = query
        if self.fail:
            raise HandoverAnalysisReadError(self.fail)

    def list_analyses(self, query, *, page_size, after_updated_at=None,
                      after_handover_analysis_id=None):
        self._check(query)
        self.analysis_after = (after_updated_at, after_handover_analysis_id)
        more = after_updated_at is None
        return HandoverAnalysisPage(
            (ANALYSIS_VIEW,), NOW if more else None,
            ANALYSIS if more else None, more,
        )

    def get_analysis(self, query, analysis_id):
        self._check(query)
        return ANALYSIS_VIEW

    def list_versions(self, query, *, handover_analysis_id, page_size,
                      after_version_no=None):
        self._check(query)
        self.version_after = after_version_no
        more = after_version_no is None
        return HandoverAnalysisVersionPage(
            (VERSION_VIEW,), 1 if more else None, more,
        )

    def get_version(self, query, *, handover_analysis_id,
                    handover_analysis_version_id):
        self._check(query)
        return VERSION_VIEW

    def list_items(self, query, *, handover_analysis_id,
                   handover_analysis_version_id, page_size,
                   after_ordinal=None):
        self._check(query)
        self.item_after = after_ordinal
        more = after_ordinal is None
        return HandoverAnalysisItemPage(
            (ITEM_VIEW,), 0 if more else None, more,
        )


class HandoverReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.reads.fail = None
        router = create_handover_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads,
            analysis_cursors=HandoverAnalysisCursorCodec(b"a" * 32),
            version_cursors=HandoverVersionCursorCodec(b"v" * 32),
            item_cursors=HandoverItemCursorCodec(b"i" * 32),
        )
        self.client = TestClient(
            create_app(handover_read_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.root = f"/api/v1/projects/{PROJECT}/handover-analyses"

    def test_default_closed_and_three_cursor_families(self):
        paths = (
            self.root, f"{self.root}/{ANALYSIS}",
            f"{self.root}/{ANALYSIS}/versions",
            f"{self.root}/{ANALYSIS}/versions/{VERSION}",
            f"{self.root}/{ANALYSIS}/versions/{VERSION}/items",
        )
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for path in paths:
                self.assertEqual(404, bare.get(path).status_code)
        for path, attr, expected in (
            (self.root, "analysis_after", (NOW, ANALYSIS)),
            (f"{self.root}/{ANALYSIS}/versions", "version_after", 1),
            (f"{self.root}/{ANALYSIS}/versions/{VERSION}/items", "item_after", 0),
        ):
            first = self.client.get(path + "?page_size=1", headers=self.headers)
            self.assertEqual(200, first.status_code)
            cursor = first.json()["data"]["next_cursor"]
            second = self.client.get(
                path + f"?page_size=1&cursor={cursor}", headers=self.headers,
            )
            self.assertEqual(200, second.status_code)
            self.assertEqual(expected, getattr(self.reads, attr))

    def test_five_safe_projections(self):
        analysis = self.client.get(f"{self.root}/{ANALYSIS}", headers=self.headers)
        versions = self.client.get(
            f"{self.root}/{ANALYSIS}/versions", headers=self.headers,
        )
        version = self.client.get(
            f"{self.root}/{ANALYSIS}/versions/{VERSION}", headers=self.headers,
        )
        items = self.client.get(
            f"{self.root}/{ANALYSIS}/versions/{VERSION}/items",
            headers=self.headers,
        )
        self.assertEqual('"v0"', analysis.headers["etag"])
        self.assertEqual(str(ANALYSIS), analysis.json()["data"][
            "handover_analysis_id"])
        self.assertEqual(str(VERSION), versions.json()["data"]["items"][0][
            "handover_analysis_version_id"])
        self.assertEqual(str(DOCUMENT_VERSION), version.json()["data"][
            "source_documents"][0]["document_version_id"])
        self.assertEqual("scope", items.json()["data"]["items"][0][
            "required_input_spec"]["required"][0])
        self.assertNotIn("path", version.text.lower())

    def test_strict_query_path_session_host_and_cursor_context(self):
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1", headers=self.headers,
        ).status_code)
        self.assertEqual(422, self.client.get(
            self.root + "?page_size=0", headers=self.headers,
        ).status_code)
        self.assertEqual(400, self.client.get(
            f"{self.root}/{ANALYSIS}?extra=1", headers=self.headers,
        ).status_code)
        self.assertEqual(422, self.client.get(
            f"{self.root}/{str(ANALYSIS).upper()}", headers=self.headers,
        ).status_code)
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.get(
            self.root, headers={**self.headers, "host": "evil.test"},
        ).status_code)
        first = self.client.get(self.root + "?page_size=1", headers=self.headers)
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            f"/api/v1/projects/{uuid.uuid4()}/handover-analyses"
            f"?page_size=1&cursor={cursor}", headers=self.headers,
        ).status_code)

    def test_safe_error_mapping(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("VALIDATION_FAILED", 422),
            ("PROJECT_ARCHIVED", 409), ("HANDOVER_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.fail = code
                response = self.client.get(self.root, headers=self.headers)
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
