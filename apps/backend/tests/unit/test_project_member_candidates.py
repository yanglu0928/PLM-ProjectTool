from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.auth.domain.username import normalize_username
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.member_candidates import (
    MemberCandidateQuery, ProjectMemberCandidateError, ProjectMemberCandidateService,
)


class Tx:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.commits += 1


class Access:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.target = uuid.uuid4()
        self.found = True
        self.lookups = 0

    def canonical_username(self, raw):
        return normalize_username(raw).normalized

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor

    def enabled_user(self, _tx, *, normalized_username):
        self.lookups += 1
        assert normalized_username == "target"
        return (self.target, "Target") if self.found else None


class Facts:
    def __init__(self):
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"

    def actor_facts(self, _tx, **kwargs):
        assert kwargs["lock"] is True
        return None if self.role is None else ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("no target resource")


class Guard:
    denied = False

    def require_valid(self, **_kwargs):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")


class Membership:
    unassigned = True
    calls = 0

    def is_unassigned(self, _tx, *, user_id):
        self.calls += 1
        return self.unassigned


class Rate:
    def __init__(self):
        self.calls = []
        self.deny_limit = None

    def reserve(self, _tx, *, bucket_key, limit, window):
        self.calls.append((bucket_key, limit, window))
        return self.deny_limit != limit


class ProjectMemberCandidateTests(unittest.TestCase):
    def setUp(self):
        self.access, self.facts, self.guard = Access(), Facts(), Guard()
        self.membership, self.rate = Membership(), Rate()
        self.membership.unassigned = True
        self.membership.calls = 0
        self.service = ProjectMemberCandidateService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=ProjectAuthorizationService(unit_of_work=Tx, repository=self.facts),
            membership=self.membership, rate=self.rate,
            clock=lambda: datetime(2026, 9, 28, tzinfo=timezone.utc),
        )
        self.query = MemberCandidateQuery(b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), " TARGET ")

    def code(self, expected):
        with self.assertRaises(ProjectMemberCandidateError) as caught:
            self.service.exact(self.query)
        self.assertEqual(caught.exception.code, expected)

    def test_exact_hit_and_digest_only_bounded_rates(self):
        candidate = self.service.exact(self.query)
        self.assertEqual((candidate.user_id, candidate.display_name), (self.access.target, "Target"))
        self.assertEqual([item[1] for item in self.rate.calls], [30, 10])
        self.assertTrue(all(len(item[0]) == 32 and b"target" not in item[0] for item in self.rate.calls))
        self.assertEqual(self.access.lookups, 1)

    def test_absent_and_assigned_have_same_result(self):
        self.access.found = False
        self.assertIsNone(self.service.exact(self.query))
        self.access.found = True
        self.membership.unassigned = False
        self.assertIsNone(self.service.exact(self.query))
        self.assertEqual(len(self.rate.calls), 4)

    def test_non_manager_other_project_archived_and_session_rejected_before_lookup_or_rate(self):
        for role, state, actor, code in (
            ("CUSTOMER_MANAGER", "ACTIVE", self.access.actor, "RESOURCE_NOT_FOUND"),
            ("PROJECT_MANAGER", "ARCHIVED", self.access.actor, "PROJECT_ARCHIVED"),
            (None, "ACTIVE", self.access.actor, "RESOURCE_NOT_FOUND"),
            ("PROJECT_MANAGER", "ACTIVE", None, "AUTH_ACCESS_DENIED"),
        ):
            self.facts.role, self.facts.state, self.access.actor = role, state, actor
            with self.subTest(role=role, state=state):
                self.code(code)
        self.assertEqual(self.access.lookups, 0)
        self.assertEqual(len(self.rate.calls), 0)

    def test_invalid_input_and_license_do_not_lookup(self):
        invalid = MemberCandidateQuery(b"s" * 32, b"c" * 32, uuid.uuid4(), self.query.project_id, "\x00")
        with self.assertRaises(ProjectMemberCandidateError) as caught:
            self.service.exact(invalid)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.guard.denied = True
        with self.assertRaises(RuntimeLicenseError):
            self.service.exact(self.query)
        self.assertEqual(self.access.lookups, 0)
        self.assertEqual(len(self.rate.calls), 0)

    def test_target_and_actor_rate_denials_prevent_lookup(self):
        self.rate.deny_limit = 10
        self.code("AUTH_RATE_LIMITED")
        self.assertEqual([item[1] for item in self.rate.calls], [30, 10])
        self.rate.calls.clear()
        self.rate.deny_limit = 30
        self.code("AUTH_RATE_LIMITED")
        self.assertEqual([item[1] for item in self.rate.calls], [30])
        self.assertEqual(self.access.lookups, 0)


if __name__ == "__main__":
    unittest.main()
