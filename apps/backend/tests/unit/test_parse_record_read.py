from __future__ import annotations

import unittest
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadQuery, DocumentReadService,
    DocumentVersionView, DocumentView, ParseRecordPage, ParseRecordView,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Access:
    def __init__(self, actor: uuid.UUID, admin: bool = False,
                 member: bool = True) -> None:
        self.actor, self.admin, self.member = actor, admin, member

    def authenticated_user(self, transaction, *, session_token, now):
        return self.actor

    def authorized_admin(self, transaction, *, session_token, now):
        return self.actor if self.admin else None

    def actor_facts(self, transaction, *, user_id, project_id, lock=False):
        return ProjectActorFacts("ACTIVE", "CUSTOMER_MEMBER") if self.member else None


class _Guard:
    def __init__(self) -> None:
        self.calls = 0

    def require_valid(self, *, trace_id):
        self.calls += 1


class _Repository:
    def __init__(self, document_id, version_id, page) -> None:
        self.document_id, self.version_id, self.page = document_id, version_id, page
        self.list_calls = 0

    def get(self, transaction, *, scope, project_id, document_id):
        if document_id != self.document_id:
            return None
        return DocumentView(document_id, scope, project_id, "PROJECT_RECORD", None,
                            "sample", "sample.pdf", "ACTIVE", self.version_id,
                            self.version_id, datetime.now(timezone.utc), '"v0"')

    def get_version(self, transaction, *, scope, project_id, document_id,
                    document_version_id):
        if document_version_id != self.version_id or document_id != self.document_id:
            return None
        return DocumentVersionView(document_version_id, document_id, 1, "a" * 64,
                                   1, "application/pdf", "AVAILABLE", None,
                                   datetime.now(timezone.utc), None)

    def list_parses(self, transaction, *, scope, project_id, document_version_id,
                    before, limit):
        self.list_calls += 1
        return self.page


class ParseRecordReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", self.project_id)
        self.item = ParseRecordView(uuid.uuid4(), self.version_id, "PDF", "1.0",
                                    "SUCCEEDED", 1, uuid.uuid4(), uuid.uuid4(),
                                    None, False, datetime.now(timezone.utc),
                                    datetime.now(timezone.utc), datetime.now(timezone.utc))
        self.repo = _Repository(self.document_id, self.version_id,
                                ParseRecordPage((self.item,), None, False))
        self.access = _Access(self.actor)
        self.guard = _Guard()
        self.service = DocumentReadService(
            unit_of_work=lambda: nullcontext(object()), session_access=self.access,
            admin_access=self.access, project_facts=self.access,
            license_guard=self.guard, repository=self.repo,
        )

    def test_authorized_fixed_version_and_safe_view(self) -> None:
        page = self.service.list_parses(self.query, self.document_id, self.version_id)
        self.assertEqual(page.items, (self.item,))
        self.assertEqual(self.repo.list_calls, 1)
        self.assertFalse(hasattr(page.items[0], "storage_locator"))
        self.assertFalse(hasattr(page.items[0], "result_sha256"))

    def test_missing_version_and_cross_project_hidden(self) -> None:
        with self.assertRaises(DocumentReadError) as missing:
            self.service.list_parses(self.query, self.document_id, uuid.uuid4())
        self.assertEqual(missing.exception.code, "RESOURCE_NOT_FOUND")
        self.access.member = False
        with self.assertRaises(DocumentReadError) as denied:
            self.service.list_parses(self.query, self.document_id, self.version_id)
        self.assertEqual(denied.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repo.list_calls, 0)

    def test_global_requires_admin(self) -> None:
        query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "GLOBAL", None)
        with self.assertRaises(DocumentReadError) as denied:
            self.service.list_parses(query, self.document_id, self.version_id)
        self.assertEqual(denied.exception.code, "RESOURCE_NOT_FOUND")
        self.access.admin = True
        self.assertEqual(len(self.service.list_parses(query, self.document_id,
                                                      self.version_id).items), 1)

    def test_invalid_cursor_or_limit_rejected_before_license(self) -> None:
        for before, limit in ((None, True), (None, 201),
                              ((datetime.now(), uuid.uuid4()), 50),
                              ((datetime.now(timezone.utc), uuid.UUID(int=0)), 50)):
            with self.subTest(before=before, limit=limit), self.assertRaises(DocumentReadError):
                self.service.list_parses(self.query, self.document_id, self.version_id,
                                         before=before, limit=limit)
        self.assertEqual(self.guard.calls, 0)


if __name__ == "__main__":
    unittest.main()
