from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.review.api.list_cursor import ReviewListCursorCodec
from plm_assistant.modules.review.api.list_reviews import create_review_list_router
from plm_assistant.modules.review.application.list_contract import (
    MyReviewAssignmentSummary,
    ReviewListActiveRoundSummary,
    ReviewListItem,
    ReviewListPage,
    ReviewListPosition,
)
from plm_assistant.modules.review.application.list_service import ReviewListError


NOW = datetime(2026, 10, 19, 8, 30, 1, 123456, tzinfo=timezone.utc)
PROJECT = uuid.uuid4()
SESSION = b"s" * 32


def _item(age: int, *, terminal: bool = False) -> ReviewListItem:
    assignment = MyReviewAssignmentSummary(uuid.uuid4(), "PENDING", None, None)
    active = None if terminal else ReviewListActiveRoundSummary(
        uuid.uuid4(), 2, uuid.uuid4(), NOW - timedelta(seconds=age), assignment,
    )
    return ReviewListItem(
        uuid.uuid4(), PROJECT, "SOL-06", uuid.uuid4(),
        "STRUCTURED_SPEC_ALL_V1", "APPROVED" if terminal else "IN_REVIEW",
        uuid.uuid4(), NOW - timedelta(seconds=age),
        '"v3"' if terminal else '"v1"', active,
    )


class Lists:
    def __init__(self) -> None:
        self.fail = None
        self.last = None
        self.result = None

    def list(self, query):
        self.last = query
        if self.fail is not None:
            raise ReviewListError(self.fail)
        return self.result


class ReviewListApiTests(unittest.TestCase):
    def setUp(self):
        self.codec = ReviewListCursorCodec(b"r" * 32)
        self.lists = Lists()
        self.visible = _item(2)
        self.terminal = _item(3, terminal=True)
        self.hidden_position = ReviewListPosition(
            NOW - timedelta(seconds=4), uuid.uuid4(),
        )
        self.lists.result = ReviewListPage(
            (self.visible, self.terminal), self.hidden_position, True,
        )
        router = create_review_list_router(
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            lists=self.lists,
            cursors=self.codec,
        )
        self.client = TestClient(
            create_app(review_list_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{PROJECT}/reviews"
        self.headers = {"cookie": "plm_session=" + SESSION.hex()}

    def test_default_closed_minimal_projection_and_encrypted_raw_position(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(
                404, bare.get(self.path, headers=self.headers).status_code,
            )
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual("nosniff", response.headers["x-content-type-options"])
        self.assertEqual("all", self.lists.last.view)
        self.assertEqual(50, self.lists.last.page_size)
        self.assertIsNone(self.lists.last.before)
        data = response.json()["data"]
        self.assertEqual({"items", "next_cursor", "has_more"}, set(data))
        self.assertTrue(data["has_more"])
        self.assertEqual(2, len(data["items"]))
        first = data["items"][0]
        self.assertEqual({
            "review_id", "project_id", "subject_ref", "policy_code",
            "state", "created_by", "created_at", "etag", "active_round",
        }, set(first))
        self.assertEqual(
            {"resource_type", "resource_id"}, set(first["subject_ref"]),
        )
        self.assertEqual({
            "review_round_id", "round_no", "subject_version_ref",
            "started_at", "my_assignment",
        }, set(first["active_round"]))
        self.assertEqual({
            "assignment_id", "state", "decision", "decided_at",
        }, set(first["active_round"]["my_assignment"]))
        self.assertIsNone(data["items"][1]["active_round"])
        self.assertEqual(
            self.hidden_position,
            self.codec.decode(
                data["next_cursor"], session_token=SESSION,
                project_id=PROJECT, view="all", page_size=50,
            ),
        )
        self.assertNotIn(str(self.hidden_position.review_id), data["next_cursor"])

    def test_strict_query_cursor_binding_and_security_boundary(self):
        self.assertEqual(403, self.client.get(
            self.path, headers={**self.headers, "host": "evil.test"},
        ).status_code)
        self.assertEqual(401, self.client.get(self.path).status_code)
        for suffix in (
            "?unknown=x", "?view=all&view=my_pending",
            "?page_size=1&page_size=2", "?cursor=x&cursor=y",
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(400, self.client.get(
                    self.path + suffix, headers=self.headers,
                ).status_code)
        for suffix in (
            "?page_size=0", "?page_size=201", "?page_size=01",
            "?page_size=%2B1", "?page_size=x", "?view=pending",
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(422, self.client.get(
                    self.path + suffix, headers=self.headers,
                ).status_code)
        self.assertEqual(400, self.client.get(
            self.path + "?cursor=not-a-cursor", headers=self.headers,
        ).status_code)
        token = self.codec.encode(
            session_token=SESSION, project_id=PROJECT, view="my_pending",
            page_size=25, position=self.hidden_position,
        )
        response = self.client.get(
            self.path + f"?view=my_pending&page_size=25&cursor={token}",
            headers=self.headers,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("my_pending", self.lists.last.view)
        self.assertEqual(25, self.lists.last.page_size)
        self.assertEqual(self.hidden_position, self.lists.last.before)
        self.assertEqual(400, self.client.get(
            self.path + f"?view=all&page_size=25&cursor={token}",
            headers=self.headers,
        ).status_code)
        self.assertEqual(422, self.client.get(
            self.path.replace(str(PROJECT), str(PROJECT).upper()),
            headers=self.headers,
        ).status_code)
        self.assertEqual(405, self.client.post(
            self.path, headers=self.headers,
        ).status_code)

    def test_safe_service_error_mapping_and_bad_result(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 401),
            ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("VALIDATION_FAILED", 422),
            ("REQUEST_MALFORMED", 400),
            ("REVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.lists.fail = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
        self.lists.fail = None
        for result in (None, True, ReviewListPage(
            (replace_project := _item(1),), None, False,
        )):
            if type(result) is ReviewListPage:
                object.__setattr__(replace_project, "project_id", uuid.uuid4())
            self.lists.result = result
            self.assertEqual(503, self.client.get(
                self.path, headers=self.headers,
            ).status_code)

    def test_constructor_requires_dependencies(self):
        values = dict(
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            lists=self.lists,
            cursors=self.codec,
        )
        for key in values:
            with self.subTest(key=key), self.assertRaises(ValueError):
                create_review_list_router(**(values | {key: None}))


if __name__ == "__main__":
    unittest.main()
