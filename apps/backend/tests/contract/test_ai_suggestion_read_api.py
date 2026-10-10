from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest import TestCase

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.read_suggestion import (
    create_ai_suggestion_read_router,
)
from plm_assistant.modules.ai.application.invocation_read import AIInvocationContextView
from plm_assistant.modules.ai.application.suggestion_read import (
    AISuggestionEvidenceFact,
    AISuggestionReadError,
    AISuggestionReadRecord,
    AISuggestionSourceFact,
    AISuggestionSourceLocationView,
    AISuggestionView,
)
from plm_assistant.modules.ai.application.task_read import AITaskInputView
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


ORIGIN = "https://plm.example.test"


class Reads:
    def __init__(self, value): self.value, self.query = value, None
    def get(self, query):
        self.query = query
        if isinstance(self.value, Exception): raise self.value
        return self.value


class AISuggestionReadApiTests(TestCase):
    def setUp(self) -> None:
        self.project, self.task = uuid.uuid4(), uuid.uuid4()
        document, version, parse_record = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        payload = {
            "schema_ref": "gap-output.v2", "schema_version": 2,
            "items": [{"category": "DIFFERENCE", "title": "差异",
                       "summary": "摘要", "rationale": "依据",
                       "recommendation": "建议", "source_citations": [{
                           "source_ordinal": 1, "node_ids": ["line-1"],
                       }], "confirmation": {"required": False,
                                               "question": None,
                                               "required_fields": []}}],
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()
        result_hash, source_hash = hashlib.sha256(b"result").digest(), hashlib.sha256(b"source").digest()
        record = AISuggestionReadRecord(
            self.task, self.project, uuid.uuid4(), "SUCCEEDED", "AVAILABLE", 4,
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            (AITaskInputView("DOC-02", document, version),),
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "model-v1",
            uuid.uuid4(), 3, "gap-output.v2", 2,
            AIInvocationContextView(
                uuid.uuid4(), 1, "project-documents.v1", "NONE", None, None,
            ), payload, canonical, hashlib.sha256(canonical).digest(),
            "NOT_FORMAL_FACT", ("REVIEW_REQUIRED",),
            datetime(2026, 10, 3, 15, tzinfo=timezone.utc),
            (AISuggestionEvidenceFact(
                1, "document", "DOCUMENT_VERSION", document, version, result_hash,
            ),),
            (AISuggestionSourceFact(
                1, "DOC-02", "document", "DOCUMENT_VERSION", document,
                version, self.project, parse_record, uuid.uuid4(), source_hash,
                result_hash,
            ),),
        )
        location = AISuggestionSourceLocationView(
            1, document, version, "PARSED_NODE",
            f"/api/v1/projects/{self.project}/documents/{document}/versions/{version}/content",
            ({"node_id": "line-1", "kind": "TEXT_LINE",
              "locator": {"locator_type": "STRUCTURED_NODE",
                          "parse_record_id": str(parse_record),
                          "node_id": "line-1",
                          "source_locator": {"locator_type": "TEXT_RANGE",
                                             "section_path": "plain-text-root",
                                             "start_offset": 0, "end_offset": 5,
                                             "normalized_fingerprint": "a" * 64}},
              "precision": "PARSED_NODE", "display_label": "文本文档 / 字符 0–5"},),
        )
        self.view = AISuggestionView(record, (location,))
        self.path = f"/api/v1/projects/{self.project}/ai-tasks/{self.task}/suggestion"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "host": "plm.example.test",
        }

    def client(self, value=None):
        reads = Reads(self.view if value is None else value)
        router = create_ai_suggestion_read_router(
            reads=reads, origins=LoginOriginPolicy([ORIGIN]),
        )
        client = TestClient(create_app(ai_suggestion_read_router=router), base_url=ORIGIN)
        client.reads = reads
        return client

    def test_default_closed_and_returns_bounded_locator_projection(self):
        with TestClient(create_app(), base_url=ORIGIN) as closed:
            self.assertEqual(closed.get(self.path, headers=self.headers).status_code, 404)
        with self.client() as client:
            response = client.get(self.path, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()["data"]
            self.assertEqual(data["fact_status"], "NOT_FORMAL_FACT")
            self.assertEqual(data["source_locations"][0]["precision"], "PARSED_NODE")
            self.assertEqual(data["payload"]["schema_version"], 2)
            self.assertEqual(response.headers["etag"], '"v4"')
            for forbidden in ("secret", "response_fingerprint", "provider_request_ref",
                              "storage_path", "source_fingerprint"):
                self.assertNotIn(forbidden, response.text.lower())

    def test_query_and_safe_errors(self):
        with self.client() as client:
            self.assertEqual(client.get(self.path + "?x=1", headers=self.headers).status_code, 400)
        for error, status in (
            (AISuggestionReadError("AUTH_ACCESS_DENIED"), 401),
            (AISuggestionReadError("RESOURCE_NOT_FOUND"), 404),
            (AISuggestionReadError("LICENSE_OPERATION_DENIED"), 403),
            (AISuggestionReadError(), 503),
        ):
            with self.subTest(status=status), self.client(error) as client:
                self.assertEqual(client.get(self.path, headers=self.headers).status_code, status)


if __name__ == "__main__":
    import unittest
    unittest.main()
