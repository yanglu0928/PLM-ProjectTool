from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.evidence.api.read_evidence import create_evidence_read_router
from plm_assistant.modules.evidence.application.read_evidence import (
    EvidencePage, EvidenceReadError, EvidenceView,
)


class _Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class _Evidence:
    def __init__(self):
        self.project = uuid.uuid4()
        self.failure = None
        self.calls = []
        self.items = tuple(EvidenceView(
            uuid.uuid4(), "PROJECT", self.project, uuid.uuid4(), uuid.uuid4(),
            {"locator_type": "DOCUMENT"}, b"x" * 32,
            f"证据 {number}", "短摘录", "CANDIDATE",
            datetime(2026, 10, 1, tzinfo=timezone.utc), '"v0"',
        ) for number in range(2))

    def list(self, query, *, after, limit):
        self.calls.append(("list", query, after, limit))
        if self.failure:
            raise EvidenceReadError(self.failure)
        if query.scope == "GLOBAL":
            return EvidencePage((), None, False)
        if after is None:
            return EvidencePage((self.items[0],),
                                (self.items[0].created_at, self.items[0].evidence_id), True)
        return EvidencePage((self.items[1],), None, False)

    def get(self, query, evidence_id):
        self.calls.append(("get", query, evidence_id))
        if self.failure:
            raise EvidenceReadError(self.failure)
        if evidence_id != self.items[0].evidence_id or query.project_id != self.project:
            raise EvidenceReadError("RESOURCE_NOT_FOUND")
        return self.items[0]


class EvidenceReadApiTests(unittest.TestCase):
    def setUp(self):
        self.evidence = _Evidence()
        self.router = create_evidence_read_router(
            sessions=_Sessions(), evidence=self.evidence,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=EvidenceListCursorCodec(b"e" * 32),
        )
        self.client = TestClient(create_app(evidence_read_router=self.router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.path = f"/api/v1/projects/{self.evidence.project}/evidence"

    def test_default_closed_and_two_page_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["data"]["items"][0]["display_excerpt"], "短摘录")
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(self.path + "?page_size=1&cursor=" + cursor,
                                 headers=self.headers)
        self.assertEqual(second.status_code, 200)
        self.assertIsNone(second.json()["data"]["next_cursor"])
        self.assertEqual(self.evidence.calls[-1][2],
                         (self.evidence.items[0].created_at, self.evidence.items[0].evidence_id))
        self.assertNotIn("storage_locator", first.text)

    def test_detail_minimal_and_global_path(self):
        detail = self.client.get(self.path + "/" + str(self.evidence.items[0].evidence_id),
                                 headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.headers["etag"], '"v0"')
        self.assertNotIn("display_excerpt", detail.json()["data"])
        self.assertEqual(self.client.get("/api/v1/global/evidence",
                                         headers=self.headers).status_code, 200)
        missing = self.client.get(self.path + "/" + str(uuid.uuid4()), headers=self.headers)
        self.assertEqual(missing.status_code, 404)

    def test_session_cursor_and_query_fail_closed(self):
        self.assertEqual(self.client.get(self.path).status_code, 401)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        cursor = first.json()["data"]["next_cursor"]
        for suffix, status in (("?page_size=1&page_size=2", 400),
                               ("?unknown=1", 400), ("?page_size=0", 422),
                               ("?page_size=2&cursor=" + cursor, 400),
                               ("?cursor=not-a-cursor", 400)):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.client.get(self.path + suffix,
                                                 headers=self.headers).status_code, status)

    def test_license_and_scope_error_mapping(self):
        for code, status in (("LICENSE_OPERATION_DENIED", 403),
                             ("RESOURCE_NOT_FOUND", 404),
                             ("EVIDENCE_UNAVAILABLE", 503)):
            self.evidence.failure = code
            with self.subTest(code=code):
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
