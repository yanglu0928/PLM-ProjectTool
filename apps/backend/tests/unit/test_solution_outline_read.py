from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.solution.application.read_outline import (
    OutlineCurrentView, OutlineListPage, OutlineReadError, OutlineReadQuery,
    OutlineReadService, OutlineSummaryView,
)
from plm_assistant.modules.solution.infrastructure.outline_read_repository import (
    SqlAlchemyOutlineReadRepository,
)


PROJECT, OUTLINE, ACTOR, VERSION = (uuid.uuid4() for _ in range(4))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
VIEW = OutlineCurrentView(OUTLINE, PROJECT, "Outline", "ACTIVE", None,
                          ACTOR, NOW, '"v0"')
SUMMARY = OutlineSummaryView(OUTLINE, PROJECT, "Outline", "ACTIVE", None,
                             NOW, '"v0"')


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
    page = OutlineListPage((SUMMARY,), None, False)
    calls = 0

    def get_current(self, tx, *, project_id, outline_id):
        self.calls += 1
        assert project_id == PROJECT and outline_id == OUTLINE
        return self.view

    def list_current(self, tx, *, project_id, after_outline_id, limit):
        self.calls += 1
        assert project_id == PROJECT and after_outline_id is None and limit == 50
        return self.page


class OutlineReadTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.facts, self.repo = (
            Access(), Guard(), Facts(), Repo())
        self.service = OutlineReadService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=Tx, repository=self.facts),
            repository=self.repo, clock=lambda: NOW)
        self.query = OutlineReadQuery(b"s" * 32, uuid.uuid4(), PROJECT)

    def rejects(self, code, query=None, identity=OUTLINE):
        with self.assertRaises(OutlineReadError) as caught:
            self.service.get_current(query or self.query, identity)
        self.assertEqual(caught.exception.code, code)

    def test_current_root_and_empty_or_approved_pointer(self):
        self.assertEqual(self.service.get_current(self.query, OUTLINE), VIEW)
        self.repo.view = replace(VIEW, current_approved_version_ref=VERSION,
                                 etag='"v2"')
        self.assertEqual(self.service.get_current(self.query, OUTLINE), self.repo.view)

    def test_validation_session_role_and_license(self):
        self.rejects("VALIDATION_FAILED", replace(self.query, session_token=b"x"))
        self.rejects("RESOURCE_NOT_FOUND", identity=uuid.UUID(int=0))
        self.access.actor = None
        self.rejects("AUTH_ACCESS_DENIED")
        self.access.actor = ACTOR
        self.facts.role = "CUSTOMER_MEMBER"
        self.assertEqual(self.service.get_current(self.query, OUTLINE), VIEW)
        self.facts.role = None
        self.rejects("RESOURCE_NOT_FOUND")
        self.facts.role = "PROJECT_MANAGER"
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED")

    def test_missing_and_inconsistent_projection_fail_closed(self):
        self.repo.view = None
        self.rejects("RESOURCE_NOT_FOUND")
        for bad in (
            replace(VIEW, project_id=uuid.uuid4()),
            replace(VIEW, solution_outline_id=uuid.uuid4()),
            replace(VIEW, current_approved_version_ref=uuid.UUID(int=0)),
            replace(VIEW, outline_state="DRAFT"),
            replace(VIEW, etag='"v01"'),
        ):
            with self.subTest(bad=bad):
                self.repo.view = bad
                self.rejects("SOLUTION_UNAVAILABLE")

    def test_repository_rejects_false_approved_pointer(self):
        root = SimpleNamespace(
            solution_outline_id=OUTLINE, project_id=PROJECT, name="Outline",
            outline_state="ACTIVE", current_approved_version_ref=VERSION,
            created_by=ACTOR, created_at=NOW, lock_version=1)
        version = SimpleNamespace(
            solution_outline_version_id=VERSION, solution_outline_id=OUTLINE,
            project_id=PROJECT, version_state="DRAFT",
            review_ref=None, review_round_ref=None)

        class Result:
            def __init__(self, value):
                self.value = value

            def one_or_none(self):
                return self.value

        class Session:
            def __init__(self, value):
                self.value = value

            def execute(self, statement):
                return Result(self.value)

        repository = SqlAlchemyOutlineReadRepository()
        for pair in ((root, None), (root, version)):
            with self.subTest(pair=pair), patch(
                "plm_assistant.modules.solution.infrastructure.outline_read_repository._session",
                return_value=Session(pair)), self.assertRaises(RuntimeError):
                repository.get_current(object(), project_id=PROJECT,
                                       outline_id=OUTLINE)
        version.version_state = "APPROVED"
        version.review_ref = uuid.uuid4()
        version.review_round_ref = uuid.uuid4()
        with patch(
            "plm_assistant.modules.solution.infrastructure.outline_read_repository._session",
            return_value=Session((root, version))):
            approved = repository.get_current(
                object(), project_id=PROJECT, outline_id=OUTLINE)
        self.assertEqual(approved.current_approved_version_ref, VERSION)
        self.assertEqual(approved.etag, '"v1"')

    def test_list_member_license_and_page_contract(self):
        self.assertEqual(self.service.list_current(self.query).items, (SUMMARY,))
        self.facts.role = "CUSTOMER_MEMBER"
        self.assertEqual(self.service.list_current(self.query).items, (SUMMARY,))
        self.facts.role = None
        with self.assertRaises(OutlineReadError) as denied:
            self.service.list_current(self.query)
        self.assertEqual(denied.exception.code, "RESOURCE_NOT_FOUND")
        self.facts.role = "PROJECT_MANAGER"
        for bad in (
            OutlineListPage((replace(SUMMARY, project_id=uuid.uuid4()),), None, False),
            OutlineListPage((SUMMARY,), OUTLINE, False),
            OutlineListPage((), OUTLINE, True),
            OutlineListPage((SUMMARY,), uuid.uuid4(), True),
            OutlineListPage((SUMMARY, SUMMARY), None, False),
            OutlineListPage((replace(SUMMARY, etag='"v01"'),), None, False),
        ):
            with self.subTest(bad=bad):
                self.repo.page = bad
                with self.assertRaises(OutlineReadError) as caught:
                    self.service.list_current(self.query)
                self.assertEqual(caught.exception.code, "SOLUTION_UNAVAILABLE")
        self.repo.page = OutlineListPage((SUMMARY,), None, False)
        self.guard.denied = True
        with self.assertRaises(OutlineReadError) as denied:
            self.service.list_current(self.query)
        self.assertEqual(denied.exception.code, "LICENSE_OPERATION_DENIED")

    def test_list_invalid_limits_and_after(self):
        for kwargs in ({"limit": 0}, {"limit": 101}, {"limit": True},
                       {"after_outline_id": uuid.UUID(int=0)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(
                    OutlineReadError) as caught:
                self.service.list_current(self.query, **kwargs)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
