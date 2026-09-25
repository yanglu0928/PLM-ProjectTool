from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.read_members import (
    MemberFacts, ProjectMemberListQuery, ProjectMemberReadError,
    ProjectMemberReadService,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    def __init__(self):
        self.user_id = uuid.uuid4()
        self.names = {}

    def authenticated_user(self, *_args, **_kwargs):
        return self.user_id

    def display_names(self, _tx, user_ids):
        return {uid: self.names[uid] for uid in user_ids if uid in self.names}


class Guard:
    def __init__(self):
        self.calls = 0
        self.denied = False

    def require_valid(self, **_kwargs):
        self.calls += 1
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")


class AuthorizationFacts:
    def __init__(self):
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"

    def actor_facts(self, _tx, **_kwargs):
        return None if self.role is None else ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("member list has no target resource")


class Repo:
    def __init__(self, project_id):
        self.project_id = project_id
        self.facts = ()
        self.calls = 0
        self.last_limit = None

    def list_page(self, _tx, *, project_id, after_member_id, limit):
        self.calls += 1
        self.last_limit = limit
        return self.facts


class ProjectMemberReadTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.access, self.guard, self.facts = Access(), Guard(), AuthorizationFacts()
        self.repo = Repo(self.project_id)
        authorization = ProjectAuthorizationService(unit_of_work=Tx, repository=self.facts)
        self.service = ProjectMemberReadService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=authorization, repository=self.repo,
        )
        self.query = ProjectMemberListQuery(b"s" * 32, uuid.uuid4(), self.project_id, limit=2)

    def member(self, state="ACTIVE", project_id=None):
        uid = uuid.uuid4()
        self.access.names[uid] = "Synthetic User"
        return MemberFacts(uuid.uuid4(), project_id or self.project_id, uid,
                           "PROJECT_MANAGER", uuid.uuid4(), "研发部", state,
                           datetime.now(timezone.utc), None, 3)

    def test_page_includes_history_and_internal_next_position(self):
        first, second, third = self.member(), self.member("SUSPENDED"), self.member("REMOVED")
        self.repo.facts = (first, second, third)
        page = self.service.list_page(self.query)
        self.assertEqual([item.state for item in page.items], ["ACTIVE", "SUSPENDED"])
        self.assertEqual(page.items[0].etag, '"v3"')
        self.assertEqual(page.items[0].department_name, "研发部")
        self.assertEqual(page.next_after_member_id, second.member_id)
        self.assertTrue(page.has_more)
        self.assertEqual(self.repo.last_limit, 3)

    def test_customer_manager_and_archived_can_read(self):
        self.facts.role = "CUSTOMER_MANAGER"
        self.facts.state = "ARCHIVED"
        self.repo.facts = (self.member(),)
        page = self.service.list_page(self.query)
        self.assertEqual(len(page.items), 1)
        self.assertIsNone(page.next_after_member_id)

    def test_other_roles_and_other_project_hidden(self):
        self.facts.role = "IMPLEMENTATION_MEMBER"
        with self.assertRaises(ProjectMemberReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repo.calls, 0)
        self.facts.role = "PROJECT_MANAGER"
        self.repo.facts = (self.member(project_id=uuid.uuid4()),)
        with self.assertRaises(ProjectMemberReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")

    def test_missing_user_summary_fails_closed(self):
        member = self.member()
        self.repo.facts = (member,)
        self.access.names.clear()
        with self.assertRaises(ProjectMemberReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")

    def test_bad_query_rejected_before_license(self):
        query = ProjectMemberListQuery(b"bad", uuid.uuid4(), self.project_id, limit=2)
        with self.assertRaises(ProjectMemberReadError) as caught:
            self.service.list_page(query)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)

    def test_inactive_session_denied(self):
        self.access.user_id = None
        with self.assertRaises(ProjectMemberReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.repo.calls, 0)

    def test_license_denial_is_classified(self):
        self.guard.denied = True
        with self.assertRaises(ProjectMemberReadError) as caught:
            self.service.list_page(self.query)
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")
        self.assertEqual(self.repo.calls, 0)


if __name__ == "__main__":
    unittest.main()
