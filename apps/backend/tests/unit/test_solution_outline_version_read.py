from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef, OutlineRequirementRef,
)
from plm_assistant.modules.solution.application.read_outline import OutlineCurrentView
from plm_assistant.modules.solution.application.read_outline_version import (
    OutlineVersionReadError, OutlineVersionReadQuery,
    OutlineVersionReadService,
)


PROJECT, OUTLINE, ACTOR, SECTION, REQUIREMENT, REQUIREMENT_VERSION, REFERENCE, REFERENCE_VERSION = (
    uuid.uuid4() for _ in range(8))
VERSION1, VERSION2, TRACE = (uuid.uuid4() for _ in range(3))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
ROOT = OutlineCurrentView(OUTLINE, PROJECT, "Outline", "ACTIVE", None,
                          ACTOR, NOW, '"v0"')
FIRST = OutlineVersionHistoryView(
    VERSION1, OUTLINE, PROJECT, 1, "DRAFT", b"h" * 32,
    (SECTION,), (OutlineRequirementRef(REQUIREMENT, REQUIREMENT_VERSION),),
    (OutlineReferenceRef("PROJECT", REFERENCE, REFERENCE_VERSION),),
    (), (), None, None, None, ACTOR, NOW)
SECOND = replace(FIRST, solution_outline_version_id=VERSION2,
                 version_no=2, supersedes_version_ref=VERSION1)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class Access:
    actor = ACTOR
    def authenticated_user(self, _tx, *, session_token, now):
        assert session_token == b"s" * 32 and now == NOW
        return self.actor


class Guard:
    denied = False
    def require_valid(self, *, trace_id):
        assert trace_id == TRACE
        if self.denied: raise RuntimeLicenseError("EXPIRED")
        return object()


class Facts:
    role = "PROJECT_MANAGER"
    def actor_facts(self, _tx, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT and lock is True
        return ProjectActorFacts("ACTIVE", self.role) if self.role else None
    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("unexpected target lookup")


class Outlines:
    value = ROOT
    def get_current(self, _tx, *, project_id, outline_id):
        assert project_id == PROJECT and outline_id == OUTLINE
        return self.value


class Versions:
    value = FIRST
    rows = (SECOND, FIRST)
    def get(self, _tx, *, project_id, outline_id, version_id):
        assert project_id == PROJECT and outline_id == OUTLINE and version_id == VERSION1
        return self.value
    def list(self, _tx, *, project_id, outline_id, before_version_no, limit):
        assert project_id == PROJECT and outline_id == OUTLINE
        assert limit in (2, 3)
        if before_version_no == 2: return (FIRST,)
        return self.rows


class OutlineVersionReadTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.facts = Access(), Guard(), Facts()
        self.outlines, self.versions = Outlines(), Versions()
        self.service = OutlineVersionReadService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=Tx, repository=self.facts),
            outlines=self.outlines, versions=self.versions,
            clock=lambda: NOW)
        self.query = OutlineVersionReadQuery(b"s" * 32, TRACE, PROJECT, OUTLINE)

    def rejects(self, code, action):
        with self.assertRaises(OutlineVersionReadError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_all_current_project_roles_read_fixed_history_and_page(self):
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                     "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"):
            with self.subTest(role=role):
                self.facts.role = role
                self.assertEqual(self.service.get(self.query, VERSION1), FIRST)
                page = self.service.list(self.query, page_size=1)
                self.assertEqual(page.items, (SECOND,))
                self.assertEqual(page.next_before_version_no, 2)
                self.assertTrue(page.has_more)
                older = self.service.list(self.query, page_size=2,
                                          before_version_no=2)
                self.assertEqual(older.items, (FIRST,))
                self.assertFalse(older.has_more)

    def test_invalid_session_project_membership_license_and_missing_root(self):
        self.rejects("VALIDATION_FAILED", lambda: self.service.get(
            replace(self.query, session_token=b"short"), VERSION1))
        self.rejects("RESOURCE_NOT_FOUND", lambda: self.service.get(
            self.query, uuid.UUID(int=0)))
        self.rejects("VALIDATION_FAILED", lambda: self.service.list(
            self.query, page_size=0))
        self.access.actor = None
        self.rejects("AUTH_ACCESS_DENIED", lambda: self.service.get(
            self.query, VERSION1))
        self.access.actor = ACTOR
        self.facts.role = None
        self.rejects("RESOURCE_NOT_FOUND", lambda: self.service.list(self.query))
        self.facts.role = "PROJECT_MANAGER"
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED", lambda: self.service.get(
            self.query, VERSION1))
        self.guard.denied = False
        self.outlines.value = None
        self.rejects("RESOURCE_NOT_FOUND", lambda: self.service.list(self.query))

    def test_missing_or_corrupt_version_and_list_fail_closed(self):
        self.versions.value = None
        self.rejects("RESOURCE_NOT_FOUND", lambda: self.service.get(
            self.query, VERSION1))
        for bad in (
            replace(FIRST, project_id=uuid.uuid4()),
            replace(FIRST, section_ids=()),
            replace(FIRST, content_fingerprint=b"short"),
            replace(FIRST, reference_refs=(OutlineReferenceRef(
                "INVALID", REFERENCE, REFERENCE_VERSION),)),
        ):
            with self.subTest(bad=bad):
                self.versions.value = bad
                self.rejects("SOLUTION_UNAVAILABLE", lambda: self.service.get(
                    self.query, VERSION1))
        self.versions.rows = (FIRST, SECOND)
        self.rejects("SOLUTION_UNAVAILABLE", lambda: self.service.list(
            self.query, page_size=2))
        self.versions.rows = (replace(SECOND, project_id=uuid.uuid4()), FIRST)
        self.rejects("SOLUTION_UNAVAILABLE", lambda: self.service.list(
            self.query, page_size=2))
