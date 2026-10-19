from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.plan.application.read_wbs_for_trace import (
    PlanWbsTraceIdentity, PlanWbsTraceQuery, PlanWbsTraceReadError,
    PlanWbsTraceReadService,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)


PROJECT, PLAN, VERSION, WBS, ACTOR, TRACE = (uuid.uuid4() for _ in range(6))
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
IDENTITY = PlanWbsTraceIdentity(WBS, VERSION, PLAN, PROJECT, "DRAFT", "ACTIVE")


class Access:
    actor = ACTOR

    def authenticated_user(self, tx, *, session_token, now):
        assert session_token == b"s" * 32 and now == NOW
        return self.actor


class Guard:
    denied = False

    def require_valid(self, *, trace_id):
        assert trace_id == TRACE
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Facts:
    role = "PROJECT_MANAGER"
    state = "ACTIVE"
    lock = None

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT
        self.lock = lock
        return ProjectActorFacts(self.state, self.role) if self.role else None

    def owner_project_id(self, tx, *, target, resource_id):
        raise AssertionError("unexpected target lookup")


class Repo:
    result = IDENTITY
    calls = 0

    def get_fixed(self, tx, *, project_id, wbs_item_id, plan_version_id):
        self.calls += 1
        assert project_id == PROJECT and wbs_item_id == WBS and plan_version_id == VERSION
        return self.result


class PlanWbsTraceReadTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.facts, self.repo = Access(), Guard(), Facts(), Repo()
        self.service = PlanWbsTraceReadService(
            access=self.access, license_guard=self.guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=lambda: None, repository=self.facts),
            repository=self.repo, clock=lambda: NOW)
        self.query = PlanWbsTraceQuery(b"s" * 32, TRACE, PROJECT)
        self.tx = object()

    def read(self):
        return self.service.get_for_trace(
            self.tx, self.query, wbs_item_id=WBS, plan_version_id=VERSION)

    def rejects(self, code, action):
        with self.assertRaises(PlanWbsTraceReadError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_exact_identity_and_archived_history(self):
        self.assertEqual(self.read(), IDENTITY)
        self.assertIs(self.facts.lock, True)
        self.repo.result = replace(IDENTITY, plan_state="ARCHIVED",
                                   version_state="SUPERSEDED")
        self.assertEqual(self.read(), self.repo.result)

    def test_invalid_input_fails_before_io(self):
        self.rejects("VALIDATION_FAILED", lambda: self.service.get_for_trace(
            self.tx, replace(self.query, session_token=b"short"),
            wbs_item_id=WBS, plan_version_id=VERSION))
        self.rejects("VALIDATION_FAILED", lambda: self.service.get_for_trace(
            self.tx, self.query, wbs_item_id=uuid.UUID(int=0),
            plan_version_id=VERSION))
        self.assertEqual(self.repo.calls, 0)

    def test_current_membership_license_and_session(self):
        self.facts.role = None
        self.rejects("RESOURCE_NOT_FOUND", self.read)
        self.facts.role = "PROJECT_MANAGER"
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED", self.read)
        self.guard.denied = False
        self.access.actor = None
        self.rejects("AUTH_ACCESS_DENIED", self.read)
        self.assertEqual(self.repo.calls, 0)

    def test_bad_or_restricted_identity_fails_closed(self):
        for result in (
            None,
            replace(IDENTITY, project_id=uuid.uuid4()),
            replace(IDENTITY, plan_version_id=uuid.uuid4()),
            replace(IDENTITY, wbs_item_id=uuid.uuid4()),
            replace(IDENTITY, version_state="RESTRICTED"),
            replace(IDENTITY, plan_state="DELETED"),
        ):
            with self.subTest(result=result):
                self.repo.result = result
                self.rejects("RESOURCE_NOT_FOUND", self.read)


if __name__ == "__main__":
    unittest.main()
