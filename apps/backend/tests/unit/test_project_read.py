from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.project.application.read_projects import (
    ProjectReadError, ProjectReadQuery, ProjectReadService, ProjectView,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    def __init__(self):
        self.user_id = uuid.uuid4()
        self.calls = 0

    def authenticated_user(self, *_args, **_kwargs):
        self.calls += 1
        return self.user_id


class Guard:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def require_valid(self, **_kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic invalid License")


class Repo:
    def __init__(self):
        self.view = ProjectView(uuid.uuid4(), "P1", "项目一", "ACTIVE",
                                datetime.now(timezone.utc), '"v0"')
        self.items = (self.view,)
        self.fail = False

    def list_authorized(self, *_args):
        if self.fail:
            raise RuntimeError("synthetic db unavailable")
        return self.items

    def get_authorized(self, _tx, _user_id, project_id):
        if self.fail:
            raise RuntimeError("synthetic db unavailable")
        return self.view if self.view.project_id == project_id else None


class ProjectReadTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.repo = Access(), Guard(), Repo()
        self.service = ProjectReadService(unit_of_work=Tx, access=self.access,
                                          license_guard=self.guard, repository=self.repo)
        self.query = ProjectReadQuery(b"s" * 32, uuid.uuid4())

    def test_current_list_and_detail(self):
        page = self.service.list(self.query)
        self.assertEqual(page.items, (self.repo.view,))
        self.assertIsNone(page.next_cursor)
        self.assertFalse(page.has_more)
        self.assertEqual(self.service.get(self.query, self.repo.view.project_id), self.repo.view)
        self.assertEqual(self.guard.calls, 2)
        self.assertEqual(self.access.calls, 2)

    def test_no_membership_or_foreign_detail_hidden(self):
        self.repo.items = ()
        self.assertEqual(self.service.list(self.query).items, ())
        with self.assertRaises(ProjectReadError) as caught:
            self.service.get(self.query, uuid.uuid4())
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_invalid_query_fails_before_license(self):
        with self.assertRaises(ProjectReadError) as caught:
            self.service.list(ProjectReadQuery(b"short", uuid.uuid4()))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)

    def test_invalid_project_id_hidden(self):
        with self.assertRaises(ProjectReadError) as caught:
            self.service.get(self.query, uuid.UUID(int=0))
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.guard.calls, 0)

    def test_session_denied_and_license_fail_closed(self):
        self.access.user_id = None
        with self.assertRaises(ProjectReadError) as caught:
            self.service.list(self.query)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.guard.fail = True
        with self.assertRaises(ProjectReadError) as caught:
            self.service.list(self.query)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")
        self.assertEqual(self.access.calls, 1)

    def test_database_failure_and_ambiguous_projection_fail_closed(self):
        self.repo.fail = True
        with self.assertRaises(ProjectReadError) as caught:
            self.service.get(self.query, self.repo.view.project_id)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")
        self.repo.fail = False
        self.repo.items = (self.repo.view, self.repo.view)
        with self.assertRaises(ProjectReadError) as caught:
            self.service.list(self.query)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
