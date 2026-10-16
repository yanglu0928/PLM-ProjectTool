"""Opt-in SectionVersion historical GET/LIST envelope and signed pagination."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.section_version_list_cursor import (
    SectionVersionListCursorCodec,
)
from plm_assistant.modules.solution.api.section_version_read import (
    create_section_version_read_router,
)
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView, SectionVersionPage, SectionVersionReadError,
)
from plm_assistant.modules.solution.application.section_version_input import SectionRequirementRef


PROJECT, SECTION, DOCUMENT, REQUIREMENT, REQ_VERSION, EVIDENCE, FIRST_ID, SECOND_ID, ACTOR = (
    uuid.uuid4() for _ in range(9))
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)
FIRST = SectionVersionHistoryView(
    FIRST_ID, SECTION, PROJECT, 1, "DRAFT", "Section body", DOCUMENT, None,
    b"a" * 32, (SectionRequirementRef(REQUIREMENT, REQ_VERSION),),
    (EVIDENCE,), ({"note": "资料待补"},), (), None, None, None, ACTOR, NOW)
SECOND = replace(FIRST, solution_section_version_id=SECOND_ID,
                 version_no=2, supersedes_version_ref=FIRST_ID)


class Sessions:
    def validate(self, token):
        if token not in (b"s" * 32, b"t" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    error = None
    def list(self, query, *, page_size, before_version_no):
        if self.error:
            raise SectionVersionReadError(self.error)
        values = (SECOND, FIRST) if before_version_no is None else (FIRST,)
        items = values[:page_size]
        more = len(values) > page_size
        return SectionVersionPage(items,
                                  items[-1].version_no if more else None, more)
    def get(self, query, version_id):
        if self.error:
            raise SectionVersionReadError(self.error)
        return FIRST if version_id == FIRST_ID else SECOND


class SectionVersionReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = SectionVersionListCursorCodec(b"c" * 32)
        self.path = f"/api/v1/projects/{PROJECT}/solution-sections/{SECTION}/versions"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_section_version_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        self.client = TestClient(
            create_app(solution_section_version_read_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_minimal_list_and_fixed_detail(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
            self.assertEqual(404, bare.get(
                self.path + "/" + str(FIRST_ID), headers=self.headers).status_code)
        self.assertEqual(404, self.client.post(self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        self.assertNotIn("etag", first.headers)
        self.assertEqual(first.headers["x-trace-id"], first.json()["trace_id"])
        page = first.json()["data"]
        self.assertTrue(page["has_more"])
        self.assertEqual(str(SECOND_ID), page["items"][0]["solution_section_version_id"])
        self.assertEqual(1, page["items"][0]["declared_evidence_count"])
        self.assertNotIn("evidence_ids", page["items"][0])
        self.assertNotIn("requirement_refs", page["items"][0])
        self.assertNotIn("assumptions", page["items"][0])
        self.assertNotIn("content_document_version_ref", page["items"][0])
        second = self.client.get(self.path, params={
            "page_size": "1", "cursor": page["next_cursor"]}, headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertEqual(str(FIRST_ID), second.json()["data"]["items"][0][
            "solution_section_version_id"])
        detail = self.client.get(self.path + "/" + str(FIRST_ID), headers=self.headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual(str(DOCUMENT), detail.json()["data"]["content_document_version_ref"])
        self.assertIsNone(detail.json()["data"]["content_artifact_ref"])
        self.assertEqual([str(EVIDENCE)], detail.json()["data"]["evidence_ids"])
        self.assertEqual([{"requirement_id": str(REQUIREMENT),
                           "requirement_version_id": str(REQ_VERSION)}],
                         detail.json()["data"]["requirement_refs"])
        self.assertEqual([{"note": "资料待补"}], detail.json()["data"]["assumptions"])
        self.assertNotIn("etag", detail.headers)

    def test_cursor_request_and_cross_scope_rejections(self):
        cursor = self.codec.encode(session_token=b"s" * 32,
                                   project_id=PROJECT, section_id=SECTION,
                                   page_size=1, before_version_no=2)
        variants = (
            (self.path + "?page_size=2&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=A" + cursor[1:], self.headers, 400),
            (self.path + "?cursor=" + cursor + "&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=0", self.headers, 422),
            (self.path + "?after=2", self.headers, 400),
            (self.path + "?page_size=1&cursor=" + cursor,
             {**self.headers, "cookie": "plm_session=" + (b"t" * 32).hex()}, 400),
            (f"/api/v1/projects/{uuid.uuid4()}/solution-sections/{SECTION}/versions"
             "?page_size=1&cursor=" + cursor, self.headers, 400),
            (f"/api/v1/projects/{PROJECT}/solution-sections/{uuid.uuid4()}/versions"
             "?page_size=1&cursor=" + cursor, self.headers, 400),
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
            (self.path + "/" + str(FIRST_ID) + "?x=1", self.headers, 400),
        )
        for path, headers, expected in variants:
            with self.subTest(path=path):
                self.assertEqual(expected,
                                 self.client.get(path, headers=headers).status_code)

    def test_owner_errors_sanitized_and_create_route_not_shadowed(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("AUTH_ACCESS_DENIED", 401),
                               ("SOLUTION_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.reads.error = code
                for path in (self.path, self.path + "/" + str(FIRST_ID)):
                    response = self.client.get(path, headers=self.headers)
                    self.assertEqual(expected, response.status_code)
                    self.assertNotIn("Traceback", response.text)
        write = APIRouter()

        @write.post(self.path)
        async def existing_create():
            return JSONResponse({"data": "create-router-reached"}, status_code=201)

        read = create_section_version_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=Reads(), cursors=self.codec)
        with TestClient(create_app(
                solution_section_version_create_router=write,
                solution_section_version_read_router=read),
                base_url="https://plm.example.test") as app:
            self.assertEqual(201, app.post(self.path).status_code)


if __name__ == "__main__":
    unittest.main()
