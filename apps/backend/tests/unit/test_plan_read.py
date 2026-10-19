from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.plan.application.read_plan import (
    PlanCurrentView, PlanListPage, PlanReadError, PlanReadQuery,
    PlanReadService, PlanSummaryView,
)


PROJECT, PLAN, ACTOR = (uuid.uuid4() for _ in range(3))
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
VIEW = PlanCurrentView(PLAN, PROJECT, "Plan", "ACTIVE", None, ACTOR, NOW, '"v0"')
SUMMARY = PlanSummaryView(PLAN, PROJECT, "Plan", "ACTIVE", None, NOW, '"v0"')


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    actor = ACTOR

    def authenticated_user(self, tx, *, session_token, now):
        assert session_token == b"s" * 32 and now == NOW
        return self.actor


class Guard:
    denied = False

    def require_valid(self, *, trace_id):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Facts:
    role = "PROJECT_MANAGER"

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT and lock is True
        return ProjectActorFacts("ACTIVE", self.role) if self.role else None

    def owner_project_id(self, tx, *, target, resource_id):
        raise AssertionError("unexpected target lookup")


class Repo:
    view = VIEW
    page = PlanListPage((SUMMARY,), None, False)
    calls = 0

    def get_current(self, tx, *, project_id, plan_id):
        self.calls += 1
        assert project_id == PROJECT and plan_id == PLAN
        return self.view

    def list_current(self, tx, *, project_id, after_plan_id, limit):
        self.calls += 1
        assert project_id == PROJECT and after_plan_id is None and limit == 50
        return self.page


class PlanReadTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.facts, self.repo = (
            Access(), Guard(), Facts(), Repo())
        self.service = PlanReadService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=Tx, repository=self.facts),
            repository=self.repo, clock=lambda: NOW)
        self.query = PlanReadQuery(b"s" * 32, uuid.uuid4(), PROJECT)

    def rejects(self, code, action):
        with self.assertRaises(PlanReadError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_current_detail_and_page(self):
        self.assertEqual(self.service.get_current(self.query, PLAN), VIEW)
        self.assertEqual(self.service.list_current(self.query).items, (SUMMARY,))

    def test_invalid_input_fails_before_io(self):
        self.rejects("VALIDATION_FAILED", lambda: self.service.get_current(
            replace(self.query, session_token=b"short"), PLAN))
        self.rejects("RESOURCE_NOT_FOUND", lambda: self.service.get_current(
            self.query, uuid.UUID(int=0)))
        self.rejects("VALIDATION_FAILED", lambda: self.service.list_current(
            self.query, limit=101))
        self.assertEqual(self.repo.calls, 0)

    def test_current_authorization_and_license(self):
        self.facts.role = None
        self.rejects("RESOURCE_NOT_FOUND", lambda: self.service.get_current(self.query, PLAN))
        self.assertEqual(self.repo.calls, 0)
        self.facts.role = "PROJECT_MANAGER"
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED", lambda: self.service.list_current(self.query))
        self.assertEqual(self.repo.calls, 0)

    def test_bad_repository_output_fails_closed(self):
        self.repo.view = replace(VIEW, current_approved_version_ref=uuid.uuid4())
        self.rejects("PLAN_UNAVAILABLE", lambda: self.service.get_current(self.query, PLAN))
        self.repo.page = PlanListPage((replace(SUMMARY, etag='W/"v0"'),), None, False)
        self.rejects("PLAN_UNAVAILABLE", lambda: self.service.list_current(self.query))

    def test_page_bounds_and_order(self):
        earlier, later = sorted((uuid.uuid4(), uuid.uuid4()), key=lambda value: value.int)
        good = PlanListPage((replace(SUMMARY, plan_id=earlier),), earlier, True)
        self.service._validate_page(good, PROJECT, None, 1)
        self.rejects("PLAN_UNAVAILABLE", lambda: self.service._validate_page(
            PlanListPage((replace(SUMMARY, plan_id=later),
                          replace(SUMMARY, plan_id=earlier)), None, False),
            PROJECT, None, 2))


if __name__ == "__main__":
    unittest.main()
