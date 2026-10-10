from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceCurrentView, ReferenceDocumentRefView, ReferenceListPage, ReferenceReadError,
    ReferenceReadQuery, ReferenceReadService, ReferenceSummaryView,
)


PROJECT, REFERENCE, VERSION, ACTOR, DOCUMENT, EVIDENCE, DOC_ROOT = (
    uuid.uuid4() for _ in range(7))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
VIEW = ReferenceCurrentView(
    REFERENCE, VERSION, PROJECT, "Project Reference", "REFERENCE_ONLY", None,
    1, "DRAFT", "PLM", "PROJECT_INTERNAL", {"industry": "synthetic"},
    (DOCUMENT,), (EVIDENCE,), b"s" * 32, b"c" * 32, ACTOR, NOW, ACTOR, NOW,
    '"v0"',
    document_refs=(ReferenceDocumentRefView(DOC_ROOT, DOCUMENT),),
)
SUMMARY = ReferenceSummaryView(
    REFERENCE, VERSION, PROJECT, "Project Reference", "REFERENCE_ONLY",
    1, "DRAFT", NOW, '"v0"',
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    actor = ACTOR

    def authenticated_user(self, tx, *, session_token, now):
        assert session_token == b"t" * 32 and now == NOW
        return self.actor


class Guard:
    denied = False

    def require_valid(self, *, trace_id):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Facts:
    role = "PROJECT_MANAGER"
    state = "ACTIVE"

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        assert user_id == ACTOR and project_id == PROJECT and lock is True
        return ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, tx, *, target, resource_id):
        raise AssertionError("unexpected target lookup")


class Repo:
    view = VIEW
    page = ReferenceListPage((SUMMARY,), None, False)
    calls = 0

    def get_current(self, tx, *, project_id, reference_solution_id):
        self.calls += 1
        assert project_id == PROJECT and reference_solution_id == REFERENCE
        return self.view

    def list_current(self, tx, *, project_id, after_reference_solution_id, limit):
        self.calls += 1
        assert project_id == PROJECT and limit == 50
        assert after_reference_solution_id is None
        return self.page


class ReferenceReadTests(unittest.TestCase):
    def setUp(self):
        self.access, self.guard, self.facts, self.repo = (
            Access(), Guard(), Facts(), Repo())
        self.service = ReferenceReadService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=Tx, repository=self.facts),
            repository=self.repo, clock=lambda: NOW,
        )
        self.query = ReferenceReadQuery(b"t" * 32, uuid.uuid4(), PROJECT)

    def rejects(self, code, query=None, identity=REFERENCE):
        with self.assertRaises(ReferenceReadError) as caught:
            self.service.get_current(query or self.query, identity)
        self.assertEqual(code, caught.exception.code)

    def test_current_fixed_projection(self):
        self.assertEqual(VIEW, self.service.get_current(self.query, REFERENCE))
        self.assertEqual(1, self.repo.calls)

    def test_bad_query_role_and_license_fail_closed(self):
        self.rejects("VALIDATION_FAILED", replace(self.query, session_token=b"x"))
        self.rejects("RESOURCE_NOT_FOUND", identity=uuid.UUID(int=0))
        self.access.actor = None
        self.rejects("AUTH_ACCESS_DENIED")
        self.access.actor = ACTOR
        self.facts.role = "CUSTOMER_MEMBER"
        self.assertEqual(VIEW, self.service.get_current(self.query, REFERENCE))
        self.facts.role = None
        self.rejects("RESOURCE_NOT_FOUND")
        self.facts.role = "PROJECT_MANAGER"
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED")

    def test_missing_or_cross_project_projection_is_rejected(self):
        self.repo.view = None
        self.rejects("RESOURCE_NOT_FOUND")
        for bad in (
            replace(VIEW, project_id=uuid.uuid4()),
            replace(VIEW, scope="GLOBAL"),
            replace(VIEW, document_version_ids=()),
            replace(VIEW, document_version_ids=(DOCUMENT, DOCUMENT)),
            replace(VIEW, document_refs=()),
            replace(VIEW, document_refs=(ReferenceDocumentRefView(
                DOC_ROOT, uuid.uuid4()),)),
            replace(VIEW, evidence_ids=(EVIDENCE, EVIDENCE)),
            replace(VIEW, source_fingerprint=b"short"),
            replace(VIEW, etag='"v01"'),
        ):
            with self.subTest(bad=bad):
                self.repo.view = bad
                self.rejects("SOLUTION_UNAVAILABLE")

    def test_list_current_and_fail_closed_page_contract(self):
        self.assertEqual((SUMMARY,), self.service.list_current(self.query).items)
        self.assertEqual(1, self.repo.calls)
        self.facts.role = "CUSTOMER_MEMBER"
        self.assertEqual((SUMMARY,), self.service.list_current(self.query).items)
        self.facts.role = None
        with self.assertRaises(ReferenceReadError) as denied:
            self.service.list_current(self.query)
        self.assertEqual("RESOURCE_NOT_FOUND", denied.exception.code)
        self.facts.role = "PROJECT_MANAGER"
        for bad in (
            ReferenceListPage((replace(SUMMARY, project_id=uuid.uuid4()),), None, False),
            ReferenceListPage((SUMMARY,), REFERENCE, False),
            ReferenceListPage((), REFERENCE, True),
            ReferenceListPage((SUMMARY,), uuid.uuid4(), True),
            ReferenceListPage((SUMMARY, SUMMARY), None, False),
        ):
            with self.subTest(bad=bad):
                self.repo.page = bad
                with self.assertRaises(ReferenceReadError) as caught:
                    self.service.list_current(self.query)
                self.assertEqual("SOLUTION_UNAVAILABLE", caught.exception.code)
        self.repo.page = ReferenceListPage((SUMMARY,), None, False)
        self.guard.denied = True
        with self.assertRaises(ReferenceReadError) as license_denied:
            self.service.list_current(self.query)
        self.assertEqual("LICENSE_OPERATION_DENIED", license_denied.exception.code)

    def test_list_invalid_limit_and_after(self):
        for kwargs in ({"limit": 0}, {"limit": 101},
                       {"after_reference_solution_id": uuid.UUID(int=0)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(
                    ReferenceReadError) as caught:
                self.service.list_current(self.query, **kwargs)
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
