from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.read_global_reference import (
    GlobalReferenceCurrentView, GlobalReferenceListPage,
    GlobalReferenceReadError, GlobalReferenceReadQuery,
    GlobalReferenceReadService, GlobalReferenceSummaryView,
)
from plm_assistant.modules.solution.application.read_reference import ReferenceDocumentRefView


REFERENCE, VERSION, ACTOR, DOCUMENT, EVIDENCE, DOC_ROOT, CONFIRMATION = (
    uuid.uuid4() for _ in range(7))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
VIEW = GlobalReferenceCurrentView(
    REFERENCE, VERSION, "Global Reference", "REFERENCE_ONLY", None,
    1, "DRAFT", "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
    (ReferenceDocumentRefView(DOC_ROOT, DOCUMENT),), (EVIDENCE,),
    b"s" * 32, b"c" * 32, CONFIRMATION, ACTOR, NOW, ACTOR, NOW, '"v0"',
)
SUMMARY = GlobalReferenceSummaryView(
    REFERENCE, VERSION, "Global Reference", "REFERENCE_ONLY",
    1, "DRAFT", NOW, '"v0"',
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Admin:
    actor = ACTOR

    def authorized_admin(self, tx, *, session_token, now):
        assert session_token == b"t" * 32 and now == NOW
        return self.actor


class Guard:
    denied = False

    def require_valid(self, *, trace_id):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Repo:
    view = VIEW
    page = GlobalReferenceListPage((SUMMARY,), None, False)
    calls = 0

    def get_current(self, tx, *, reference_solution_id):
        self.calls += 1
        assert reference_solution_id == REFERENCE
        return self.view

    def list_current(self, tx, *, after_reference_solution_id, limit):
        self.calls += 1
        assert after_reference_solution_id is None and limit == 50
        return self.page


class GlobalReferenceReadTests(unittest.TestCase):
    def setUp(self):
        self.admin, self.guard, self.repo = Admin(), Guard(), Repo()
        self.service = GlobalReferenceReadService(
            unit_of_work=Tx, admins=self.admin,
            license_guard=self.guard, repository=self.repo,
            clock=lambda: NOW)
        self.query = GlobalReferenceReadQuery(b"t" * 32, uuid.uuid4())

    def rejects(self, code, query=None, identity=REFERENCE):
        with self.assertRaises(GlobalReferenceReadError) as caught:
            self.service.get_current(query or self.query, identity)
        self.assertEqual(code, caught.exception.code)

    def test_current_fixed_global_projection(self):
        self.assertEqual(VIEW, self.service.get_current(self.query, REFERENCE))
        self.assertEqual(1, self.repo.calls)

    def test_validation_admin_license_and_missing(self):
        self.rejects("VALIDATION_FAILED", replace(self.query, session_token=b"x"))
        self.rejects("RESOURCE_NOT_FOUND", identity=uuid.UUID(int=0))
        self.admin.actor = None
        self.rejects("RESOURCE_NOT_FOUND")
        self.assertEqual(0, self.repo.calls)
        self.admin.actor = ACTOR
        self.repo.view = None
        self.rejects("RESOURCE_NOT_FOUND")
        self.repo.view = VIEW
        self.guard.denied = True
        self.rejects("LICENSE_OPERATION_DENIED")

    def test_inconsistent_current_view_fails_closed(self):
        for bad in (
            replace(VIEW, reference_solution_id=uuid.uuid4()),
            replace(VIEW, deidentification_confirmation_id=uuid.UUID(int=0)),
            replace(VIEW, document_refs=()),
            replace(VIEW, document_refs=(ReferenceDocumentRefView(DOC_ROOT, DOCUMENT),
                                         ReferenceDocumentRefView(DOC_ROOT, DOCUMENT))),
            replace(VIEW, evidence_ids=(EVIDENCE, EVIDENCE)),
            replace(VIEW, source_fingerprint=b"short"),
            replace(VIEW, etag='"v01"'),
        ):
            with self.subTest(bad=bad):
                self.repo.view = bad
                self.rejects("SOLUTION_UNAVAILABLE")

    def test_list_page_and_bad_page(self):
        self.assertEqual((SUMMARY,), self.service.list_current(self.query).items)
        for bad in (
            GlobalReferenceListPage((SUMMARY,), REFERENCE, False),
            GlobalReferenceListPage((), REFERENCE, True),
            GlobalReferenceListPage((SUMMARY,), uuid.uuid4(), True),
            GlobalReferenceListPage((SUMMARY, SUMMARY), None, False),
            GlobalReferenceListPage((replace(SUMMARY, etag='"v01"'),), None, False),
        ):
            with self.subTest(bad=bad), self.assertRaises(
                    GlobalReferenceReadError) as caught:
                self.repo.page = bad
                self.service.list_current(self.query)
            self.assertEqual("SOLUTION_UNAVAILABLE", caught.exception.code)
        self.repo.page = GlobalReferenceListPage((SUMMARY,), None, False)
        self.admin.actor = None
        with self.assertRaises(GlobalReferenceReadError) as caught:
            self.service.list_current(self.query)
        self.assertEqual("RESOURCE_NOT_FOUND", caught.exception.code)
        self.admin.actor = ACTOR
        self.guard.denied = True
        with self.assertRaises(GlobalReferenceReadError) as caught:
            self.service.list_current(self.query)
        self.assertEqual("LICENSE_OPERATION_DENIED", caught.exception.code)

    def test_list_invalid_inputs(self):
        for kwargs in ({"limit": 0}, {"limit": 101},
                       {"after_reference_solution_id": uuid.UUID(int=0)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(
                    GlobalReferenceReadError) as caught:
                self.service.list_current(self.query, **kwargs)
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
