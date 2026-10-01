from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.evidence.application.eligibility_access import (
    EvidenceEligibilityAccess, EvidenceEligibilityAccessError,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Session:
    def __init__(self, user):
        self.user = user

    def authenticated_user(self, tx, *, session_token, csrf_token, now):
        return self.user


class _Admin:
    user = None

    def authorized_admin(self, tx, *, session_token, csrf_token, now):
        return self.user


class _Project:
    role = "PROJECT_MANAGER"
    state = "ACTIVE"
    lock = False

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        self.lock = lock
        return ProjectActorFacts(self.state, self.role) if self.role else None


class EvidenceEligibilityAccessTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project_id = uuid.uuid4(), uuid.uuid4()
        self.session, self.admin, self.project = (
            _Session(self.actor), _Admin(), _Project())
        self.access = EvidenceEligibilityAccess(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            session_access=self.session, admin_access=self.admin,
            project_facts=self.project,
        )

    def _require(self, scope="PROJECT", project_id=None):
        self.access.require_in_transaction(
            object(), actor_id=self.actor, scope=scope,
            project_id=self.project_id if project_id is None and scope == "PROJECT"
            else project_id, operation="V1_EVIDENCE_SET_ELIGIBILITY",
            session_token=b"s" * 32, csrf_token=b"c" * 32,
        )

    def test_project_manager_and_customer_manager_are_current_deciders(self):
        for role in ("PROJECT_MANAGER", "CUSTOMER_MANAGER"):
            self.project.role = role
            self._require()
            self.assertTrue(self.project.lock)

    def test_other_roles_removed_and_archived_are_denied(self):
        for role, state, expected in (
            ("IMPLEMENTATION_MEMBER", "ACTIVE", "RESOURCE_NOT_FOUND"),
            ("CUSTOMER_MEMBER", "ACTIVE", "RESOURCE_NOT_FOUND"),
            (None, "ACTIVE", "RESOURCE_NOT_FOUND"),
            ("PROJECT_MANAGER", "ARCHIVED", "PROJECT_ARCHIVED"),
        ):
            self.project.role, self.project.state = role, state
            with self.subTest(role=role, state=state):
                with self.assertRaises(EvidenceEligibilityAccessError) as caught:
                    self._require()
                self.assertEqual(caught.exception.code, expected)

    def test_session_identity_csrf_and_global_admin_boundary(self):
        self.session.user = uuid.uuid4()
        with self.assertRaises(EvidenceEligibilityAccessError) as caught:
            self._require()
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.session.user = self.actor
        with self.assertRaises(EvidenceEligibilityAccessError) as caught:
            self._require("GLOBAL")
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.admin.user = self.actor
        self._require("GLOBAL")
        with self.assertRaises(EvidenceEligibilityAccessError) as caught:
            self.access.require_in_transaction(
                object(), actor_id=self.actor, scope="GLOBAL", project_id=self.project_id,
                operation="V1_EVIDENCE_SET_ELIGIBILITY",
                session_token=b"s" * 32, csrf_token=b"c" * 32)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        with self.assertRaises(EvidenceEligibilityAccessError) as caught:
            self.access.require_in_transaction(
                object(), actor_id=self.actor, scope="PROJECT", project_id=self.project_id,
                operation="V1_EVIDENCE_SET_ELIGIBILITY",
                session_token=b"s" * 32, csrf_token=b"x" * 32)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")


if __name__ == "__main__":
    unittest.main()
