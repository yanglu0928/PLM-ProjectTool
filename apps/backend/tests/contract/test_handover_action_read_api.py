from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.handover.api.action_list_cursor import HandoverActionListCursorCodec
from plm_assistant.modules.handover.api.read_actions import create_handover_action_read_router
from plm_assistant.modules.handover.application.read_actions import (
    HandoverActionCurrentEventView, HandoverActionDetailView,
    HandoverActionEvidenceView, HandoverActionPage, HandoverActionReadError,
    HandoverActionResponseView, HandoverActionSummaryView,
)


class Sessions:
    def validate(self, token):
        if token not in (b"m" * 32, b"o" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")


class Actions:
    def __init__(self, project):
        self.project, self.calls = project, 0
        self.now = datetime(2026, 10, 5, tzinfo=timezone.utc)
        self.ids = tuple(uuid.uuid4() for _ in range(3))
        self.fail = None

    def summary(self, action_id, index=0):
        return HandoverActionSummaryView(
            action_id, self.project, "HUMAN", "PROVIDE_INFO", f"Action {index}",
            uuid.uuid4(), self.now, "HIGH", "SUBMITTED", self.now, None,
            None, None, self.now, '"v2"',
        )

    def list_page(self, query, *, page_size, after_updated_at=None,
                  after_action_item_id=None):
        self.calls += 1
        if self.fail:
            raise HandoverActionReadError(self.fail)
        if query.project_id != self.project:
            raise HandoverActionReadError("RESOURCE_NOT_FOUND")
        offset = 0 if after_action_item_id is None else self.ids.index(after_action_item_id) + 1
        items = tuple(self.summary(item, offset + index) for index, item in enumerate(
            self.ids[offset:offset + page_size],
        ))
        more = offset + page_size < len(self.ids)
        tail = items[-1] if more else None
        return HandoverActionPage(
            items, tail.updated_at if tail else None,
            tail.action_item_id if tail else None, more,
        )

    def get(self, query, action_item_id):
        self.calls += 1
        if self.fail:
            raise HandoverActionReadError(self.fail)
        if query.project_id != self.project or action_item_id not in self.ids:
            raise HandoverActionReadError("RESOURCE_NOT_FOUND")
        summary = self.summary(action_item_id)
        return HandoverActionDetailView(
            summary, None, None, "Meeting", {"fields": [{"name": "answer"}]},
            (HandoverActionResponseView(uuid.uuid4(), uuid.uuid4(), 0),),
            (HandoverActionEvidenceView(uuid.uuid4(), "SUBMISSION", 0),),
            uuid.uuid4(), "Created manually", self.now, None,
            HandoverActionCurrentEventView(
                uuid.uuid4(), 2, "IN_PROGRESS", "SUBMITTED", uuid.uuid4(),
                "Response submitted", self.now,
            ),
        )


class HandoverActionReadApiTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.actions = Actions(self.project)
        router = create_handover_action_read_router(
            sessions=Sessions(), actions=self.actions,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=HandoverActionListCursorCodec(b"k" * 32),
        )
        self.client = TestClient(
            create_app(handover_action_read_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project}/handover-action-items"
        self.cookie = "plm_session=" + (b"m" * 32).hex()

    def get(self, path, cookie=None):
        return self.client.get(path, headers={"cookie": cookie or self.cookie})

    def test_opt_in_list_detail_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        first = self.get(self.path + "?page_size=2")
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        data = first.json()["data"]
        self.assertEqual(2, len(data["items"]))
        self.assertTrue(data["has_more"])
        self.assertNotIn("requested_input_spec", data["items"][0])
        second = self.get(self.path + "?page_size=2&cursor=" + data["next_cursor"])
        self.assertEqual(1, len(second.json()["data"]["items"]))
        detail = self.get(self.path + "/" + str(self.actions.ids[0]))
        self.assertEqual(200, detail.status_code)
        self.assertEqual('"v2"', detail.headers["etag"])
        body = detail.json()["data"]
        self.assertEqual("SUBMITTED", body["current_event"]["to_state"])
        self.assertNotIn("trace_id", body["current_event"])

    def test_cursor_context_and_query_fail_before_owner(self):
        cursor = self.get(self.path + "?page_size=2").json()["data"]["next_cursor"]
        before = self.actions.calls
        bad = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        for path, cookie in (
            (self.path + "?page_size=2&cursor=" + bad, None),
            (self.path + "?page_size=3&cursor=" + cursor, None),
            (self.path + "?page_size=2&cursor=" + cursor,
             "plm_session=" + (b"o" * 32).hex()),
            (f"/api/v1/projects/{uuid.uuid4()}/handover-action-items?page_size=2&cursor=" + cursor, None),
            (self.path + "?page_size=2&page_size=3", None),
            (self.path + "?state=OPEN", None),
            (self.path + "/" + str(self.actions.ids[0]) + "?x=1", None),
        ):
            with self.subTest(path=path):
                self.assertEqual(400, self.get(path, cookie).status_code)
        self.assertEqual(before, self.actions.calls)

    def test_errors_and_resource_hiding(self):
        for code, status in (("RESOURCE_NOT_FOUND", 404),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("HANDOVER_UNAVAILABLE", 503)):
            self.actions.fail = code
            with self.subTest(code=code):
                self.assertEqual(status, self.get(self.path).status_code)
        self.actions.fail = None
        self.assertEqual(404, self.get(self.path + "/" + str(uuid.uuid4())).status_code)
        self.assertEqual(404, self.get(self.path + "/" + str(uuid.UUID(int=0))).status_code)


if __name__ == "__main__":
    unittest.main()
