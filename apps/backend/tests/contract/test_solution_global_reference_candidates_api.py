"""Project GLOBAL candidate opt-in HTTP and minimal disclosure contract."""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.global_reference_candidates import (
    create_project_global_reference_candidate_router,
)
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec, GlobalReferenceCandidateCursorError,
)
from plm_assistant.modules.solution.application.list_global_reference_candidates import (
    GlobalReferenceCandidate,
)
from plm_assistant.modules.solution.application.read_global_reference_candidates import (
    GlobalReferenceCandidateReadError, GlobalReferenceCandidateReadPage,
)


PROJECT, ROOT, VERSION = (uuid.uuid4() for _ in range(3))
ITEM = GlobalReferenceCandidate(ROOT, VERSION, "人工审定标签", 1, "ELIGIBLE")
TOKEN = b"s" * 32


class Sessions:
    def validate(self, token):
        if token != TOKEN:
            raise SessionError("AUTH_SESSION_EXPIRED")


class Reads:
    def __init__(self):
        self.codec = GlobalReferenceCandidateCursorCodec(b"k" * 32)
        self.error = None
        self.calls = []

    def list(self, query, *, page_size=20, cursor=None):
        self.calls.append((query, page_size, cursor))
        if self.error:
            raise GlobalReferenceCandidateReadError(self.error)
        if cursor is None:
            return GlobalReferenceCandidateReadPage(
                (), self.codec.encode(
                    session_token=query.session_token,
                    project_id=query.project_id, page_size=page_size,
                    after_root_id=ROOT), True)
        try:
            after = self.codec.decode(
                cursor, session_token=query.session_token,
                project_id=query.project_id, page_size=page_size)
        except GlobalReferenceCandidateCursorError:
            raise GlobalReferenceCandidateReadError("REQUEST_MALFORMED") from None
        if after != ROOT:
            raise GlobalReferenceCandidateReadError("REQUEST_MALFORMED")
        return GlobalReferenceCandidateReadPage((ITEM,), None, False)


class GlobalReferenceCandidateApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/projects/{PROJECT}/global-reference-candidates"
        self.headers = {"cookie": "plm_session=" + TOKEN.hex(),
                        "origin": "https://plm.example.test"}
        router = create_project_global_reference_candidate_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads)
        self.client = TestClient(
            create_app(project_global_reference_candidate_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_empty_page_then_minimal_candidate(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual("no-store", first.headers["cache-control"])
        self.assertEqual(first.headers["x-trace-id"], first.json()["trace_id"])
        self.assertEqual([], first.json()["data"]["items"])
        self.assertTrue(first.json()["data"]["has_more"])
        cursor = first.json()["data"]["next_cursor"]
        self.assertTrue(cursor)
        second = self.client.get(self.path, params={"page_size": "1", "cursor": cursor},
                                 headers=self.headers)
        self.assertEqual(200, second.status_code, second.text)
        data = second.json()["data"]
        self.assertFalse(data["has_more"])
        self.assertIsNone(data["next_cursor"])
        self.assertEqual({
            "reference_solution_id", "reference_version_id", "display_label",
            "version_no", "eligibility_state",
        }, set(data["items"][0]))
        self.assertEqual(str(ROOT), data["items"][0]["reference_solution_id"])
        self.assertEqual("人工审定标签", data["items"][0]["display_label"])
        self.assertNotIn("source_fingerprint", second.text)
        self.assertNotIn("original_name", second.text)
        self.assertEqual(404, self.client.post(self.path, headers=self.headers).status_code)

    def test_security_query_and_owner_errors(self):
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        cursor = first.json()["data"]["next_cursor"]
        variants = (
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
            (self.path + "?page_size=0", self.headers, 422),
            (self.path + "?page_size=101", self.headers, 422),
            (self.path + "?other=1", self.headers, 400),
            (self.path + "?cursor=A&cursor=B", self.headers, 400),
            (self.path + "?page_size=2&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=" + cursor[:-1]
             + ("A" if cursor[-1] != "A" else "B"), self.headers, 400),
        )
        for path, headers, expected in variants:
            with self.subTest(expected=expected, path=path[:95]):
                self.assertEqual(expected, self.client.get(
                    path, headers=headers).status_code)
        for code, status in (
                ("RESOURCE_NOT_FOUND", 404),
                ("LICENSE_OPERATION_DENIED", 403),
                ("PROJECT_ARCHIVED", 409)):
            with self.subTest(code=code):
                self.reads.error = code
                self.assertEqual(status, self.client.get(
                    self.path, headers=self.headers).status_code)


if __name__ == "__main__":
    unittest.main()
