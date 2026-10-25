from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.read_departments import create_project_department_read_router
from plm_assistant.modules.project.application.read_departments import (
    DepartmentPage, DepartmentView, ProjectDepartmentReadError,
)


class Sessions:
    def validate(self, token):
        if token not in (b"m" * 32, b"o" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Departments:
    def __init__(self, project_id):
        self.project_id = project_id
        self.calls = 0
        self.fail = None
        self.ids = tuple(uuid.uuid4() for _ in range(3))

    def list_page(self, query):
        self.calls += 1
        if self.fail:
            raise ProjectDepartmentReadError(self.fail)
        if query.project_id != self.project_id:
            raise ProjectDepartmentReadError("RESOURCE_NOT_FOUND")
        assert query.limit == 2
        position = 0 if query.after_department_id is None else self.ids.index(query.after_department_id) + 1
        now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        all_items = tuple(DepartmentView(
            department_id, "D", "Department", "ACTIVE", now, '"v0"',
        ) for department_id in self.ids)
        items = all_items[position:position + query.limit]
        has_more = position + query.limit < len(all_items)
        return DepartmentPage(items, items[-1].department_id if has_more else None, has_more)


class ProjectDepartmentReadApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.departments = Departments(self.project_id)
        router = create_project_department_read_router(
            sessions=Sessions(), departments=self.departments,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=DepartmentListCursorCodec(b"k" * 32),
        )
        self.client = TestClient(create_app(project_department_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}/departments"
        self.cookie = "plm_session=" + (b"m" * 32).hex()

    def get(self, path, *, cookie=None):
        return self.client.get(path, headers={"cookie": cookie or self.cookie})

    def test_default_closed_and_page_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        first = self.get(self.path + "?page_size=2")
        self.assertEqual(first.status_code, 200)
        data = first.json()["data"]
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(data["has_more"])
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(set(data["items"][0]), {
            "department_id", "code", "name", "state", "created_at", "etag",
        })
        second = self.get(self.path + "?page_size=2&cursor=" + data["next_cursor"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["data"]["items"]), 1)
        self.assertIsNone(second.json()["data"]["next_cursor"])

    def test_invalid_scope_and_query_fail_before_read(self):
        cursor = self.get(self.path + "?page_size=2").json()["data"]["next_cursor"]
        count = self.departments.calls
        tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        for path, cookie in (
            (self.path + "?page_size=2&cursor=" + tampered, None),
            (self.path + "?page_size=3&cursor=" + cursor, None),
            (self.path + "?page_size=2&cursor=" + cursor,
             "plm_session=" + (b"o" * 32).hex()),
            (f"/api/v1/projects/{uuid.uuid4()}/departments?page_size=2&cursor=" + cursor, None),
            (self.path + "?page_size=2&page_size=3", None),
            (self.path + "?order_by=code", None),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, cookie=cookie).status_code, 400)
        self.assertEqual(self.departments.calls, count)

    def test_authorization_and_license_fail_closed(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("PROJECT_UNAVAILABLE", 503)):
            self.departments.fail = code
            with self.subTest(code=code):
                self.assertEqual(self.get(self.path).status_code, expected)
        self.departments.fail = None
        self.assertEqual(self.get(f"/api/v1/projects/{uuid.uuid4()}/departments").status_code, 404)


if __name__ == "__main__":
    unittest.main()
