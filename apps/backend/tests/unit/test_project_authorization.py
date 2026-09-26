from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, POLICIES, ProjectActorFacts, ProjectAuthorizationError,
    ProjectAuthorizationService,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Repo:
    def __init__(self, project_id):
        self.project_id = project_id
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"
        self.owner = project_id
        self.calls = 0

    def actor_facts(self, transaction, *, user_id, project_id, lock=False):
        self.calls += 1
        self.last_lock = lock
        return None if self.role is None else ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, transaction, *, target, resource_id):
        self.calls += 1
        return self.owner


class ProjectAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.user = uuid.uuid4()
        self.project = uuid.uuid4()
        self.repo = Repo(self.project)
        self.service = ProjectAuthorizationService(unit_of_work=Tx, repository=self.repo)

    def check(self, operation, *, resource_id=None):
        return self.service.require(user_id=self.user, project_id=self.project,
                                    operation=operation, resource_id=resource_id)

    def test_matrix_exact_for_four_roles(self):
        self.assertEqual(len(POLICIES), 18)
        self.assertEqual(POLICIES["REVIEW_CREATE"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["REVIEW_CREATE"].write)
        self.assertEqual(POLICIES["REVIEW_GET"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["REVIEW_GET"].write)
        self.assertTrue(POLICIES["REVIEW_GET"].lock_reads)
        self.assertEqual(POLICIES["WORKFLOW_GET"].roles, ALL_MEMBERS)
        self.assertFalse(POLICIES["WORKFLOW_GET"].write)
        self.assertTrue(POLICIES["WORKFLOW_GET"].lock_reads)
        self.assertEqual(POLICIES["WORKFLOW_START"].roles, {"PROJECT_MANAGER"})
        self.assertTrue(POLICIES["WORKFLOW_START"].write)
        self.assertEqual(POLICIES["TRACE_LINK_CREATE"].roles,
                         {"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
        self.assertTrue(POLICIES["TRACE_LINK_CREATE"].write)
        self.assertEqual(len(ALL_MEMBERS), 4)
        for operation, policy in POLICIES.items():
            for role in ALL_MEMBERS:
                self.repo.role = role
                resource = uuid.uuid4() if policy.target else None
                with self.subTest(operation=operation, role=role):
                    if role in policy.roles:
                        self.assertEqual(self.check(operation, resource_id=resource).project_role, role)
                    else:
                        with self.assertRaises(ProjectAuthorizationError) as caught:
                            self.check(operation, resource_id=resource)
                        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_unknown_or_invalid_request_denied_before_repository(self):
        for operation, resource in (("UNKNOWN", None), ("PROJECT_GET", uuid.uuid4()),
                                    ("PROJECT_MEMBER_PATCH", None)):
            with self.subTest(operation=operation), self.assertRaises(ProjectAuthorizationError):
                self.check(operation, resource_id=resource)
        self.assertEqual(self.repo.calls, 0)

    def test_workflow_read_locks_current_facts_but_allows_archived_read(self):
        self.repo.state = "ARCHIVED"
        self.assertEqual(self.check("WORKFLOW_GET").operation, "WORKFLOW_GET")
        self.assertTrue(self.repo.last_lock)

    def test_missing_member_and_cross_project_target_are_hidden(self):
        self.repo.role = None
        with self.assertRaises(ProjectAuthorizationError) as missing:
            self.check("PROJECT_GET")
        self.assertEqual(missing.exception.code, "RESOURCE_NOT_FOUND")
        self.repo.role = "PROJECT_MANAGER"
        self.repo.owner = uuid.uuid4()
        with self.assertRaises(ProjectAuthorizationError) as cross:
            self.check("PROJECT_MEMBER_PATCH", resource_id=uuid.uuid4())
        self.assertEqual(cross.exception.code, "RESOURCE_NOT_FOUND")

    def test_archived_allows_read_but_denies_write(self):
        self.repo.state = "ARCHIVED"
        self.assertEqual(self.check("PROJECT_GET").operation, "PROJECT_GET")
        with self.assertRaises(ProjectAuthorizationError) as archived:
            self.check("PROJECT_PATCH")
        self.assertEqual(archived.exception.code, "PROJECT_ARCHIVED")

    def test_write_uses_locked_current_facts_in_caller_transaction(self):
        tx = Tx()
        result = self.service.require_in_transaction(
            tx, user_id=self.user, project_id=self.project, operation="PROJECT_PATCH",
        )
        self.assertEqual(result.project_role, "PROJECT_MANAGER")
        self.assertTrue(self.repo.last_lock)
        self.check("PROJECT_GET")
        self.assertFalse(self.repo.last_lock)


if __name__ == "__main__":
    unittest.main()
