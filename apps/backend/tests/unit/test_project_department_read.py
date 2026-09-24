from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import ProjectActorFacts, ProjectAuthorizationService
from plm_assistant.modules.project.application.read_departments import (
    DepartmentFacts, ProjectDepartmentListQuery, ProjectDepartmentReadError,
    ProjectDepartmentReadService,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    def __init__(self):
        self.user_id = uuid.uuid4()

    def authenticated_user(self, *_args, **_kwargs):
        return self.user_id


class Guard:
    def __init__(self):
        self.calls = 0

    def require_valid(self, **_kwargs):
        self.calls += 1


class AuthorizationFacts:
    def __init__(self):
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"

    def actor_facts(self, _tx, **_kwargs):
        return None if self.role is None else ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("Department list has no target resource")


class Repo:
    def __init__(self):
        self.facts = ()
        self.calls = 0

    def list_page(self, _tx, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.facts


class ProjectDepartmentReadTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.access, self.guard, self.auth_facts, self.repo = (
            Access(), Guard(), AuthorizationFacts(), Repo(),
        )
        authorization = ProjectAuthorizationService(unit_of_work=Tx, repository=self.auth_facts)
        self.service = ProjectDepartmentReadService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=authorization, repository=self.repo,
        )
        self.query = ProjectDepartmentListQuery(b"s" * 32, uuid.uuid4(), self.project_id, limit=2)

    def department(self, state="ACTIVE", project_id=None):
        return DepartmentFacts(
            uuid.uuid4(), project_id or self.project_id, "D1", "研发部",
            state, datetime.now(timezone.utc), 3,
        )

    def test_page_contains_active_and_inactive_history(self):
        first, second, third = self.department(), self.department("INACTIVE"), self.department()
        self.repo.facts = (first, second, third)
        page = self.service.list_page(self.query)
        self.assertEqual([item.state for item in page.items], ["ACTIVE", "INACTIVE"])
        self.assertEqual(page.items[0].etag, '"v3"')
        self.assertEqual(page.next_after_department_id, second.department_id)
        self.assertTrue(page.has_more)
        self.assertEqual(self.repo.kwargs["limit"], 3)

    def test_all_member_roles_and_archived_project_can_read(self):
        self.auth_facts.state = "ARCHIVED"
        self.repo.facts = (self.department(),)
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                     "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"):
            with self.subTest(role=role):
                self.auth_facts.role = role
                page = self.service.list_page(self.query)
                self.assertEqual(len(page.items), 1)
                self.assertFalse(page.has_more)
                self.assertIsNone(page.next_after_department_id)

    def test_other_project_and_missing_membership_hidden(self):
        self.auth_facts.role = None
        with self.assertRaises(ProjectDepartmentReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repo.calls, 0)
        self.auth_facts.role = "PROJECT_MANAGER"
        self.repo.facts = (self.department(project_id=uuid.uuid4()),)
        with self.assertRaises(ProjectDepartmentReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")

    def test_invalid_query_fails_before_license(self):
        with self.assertRaises(ProjectDepartmentReadError) as caught:
            self.service.list_page(replace(self.query, limit=201))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)

    def test_missing_session_denied(self):
        self.access.user_id = None
        with self.assertRaises(ProjectDepartmentReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.repo.calls, 0)


if __name__ == "__main__":
    unittest.main()
