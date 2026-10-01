from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadQuery, DocumentReadService,
    DocumentVersionView, DocumentView,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


class _Session:
    user = uuid.uuid4()

    def authenticated_user(self, tx, *, session_token, now):
        return self.user


class _Admin:
    def authorized_admin(self, tx, *, session_token, now):
        return None


class _Project:
    role = "PROJECT_MANAGER"
    lock = None

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        self.lock = lock
        return ProjectActorFacts("ACTIVE", self.role) if self.role else None


class _Guard:
    def require_valid(self, *, trace_id):
        return object()


class _Repository:
    def __init__(self, document_id, version_id, project_id):
        now = datetime.now(timezone.utc)
        self.version = DocumentVersionView(version_id, document_id, 1, "a" * 64,
                                           10, "application/pdf", "AVAILABLE", None,
                                           now, None)
        self.document = DocumentView(document_id, "PROJECT", project_id,
                                     "TEMPLATE", None, "T", "T", "ACTIVE",
                                     version_id, version_id, now, '"v1"')
        self.calls = []

    def get_version_for_trace(self, tx, **kwargs):
        self.calls.append(("version", tx, kwargs))
        return self.version

    def get(self, tx, **kwargs):
        self.calls.append(("document", tx, kwargs))
        return self.document


class DocumentEvidenceSourceFactsTests(unittest.TestCase):
    def setUp(self):
        self.document_id, self.version_id, self.project_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(),
                                       "PROJECT", self.project_id)
        self.repository = _Repository(self.document_id, self.version_id,
                                      self.project_id)
        self.project = _Project()
        self.service = DocumentReadService(
            unit_of_work=lambda: self.fail("nested transaction"),
            session_access=_Session(), admin_access=_Admin(),
            project_facts=self.project, license_guard=_Guard(),
            repository=self.repository,
        )
        self.tx = object()

    def _read(self):
        return self.service.get_source_facts_for_evidence(
            self.tx, self.query, self.document_id, self.version_id)

    def test_fixed_version_and_category_use_same_locked_transaction(self):
        facts = self._read()
        self.assertEqual((facts.document_category, facts.document_version_id),
                         ("TEMPLATE", self.version_id))
        self.assertTrue(self.project.lock)
        self.assertEqual([call[0] for call in self.repository.calls],
                         ["version", "document"])
        self.assertTrue(all(call[1] is self.tx for call in self.repository.calls))
        self.assertFalse(hasattr(facts, "storage_locator"))

    def test_missing_or_forged_source_fails_closed(self):
        for field, replacement in (
            ("version", None),
            ("version", replace(self.repository.version,
                                document_version_id=uuid.uuid4())),
            ("document", None),
            ("document", replace(self.repository.document, project_id=uuid.uuid4())),
            ("document", replace(self.repository.document, document_state="REVOKED")),
        ):
            original = getattr(self.repository, field)
            setattr(self.repository, field, replacement)
            try:
                with self.subTest(field=field, replacement=replacement):
                    with self.assertRaises(DocumentReadError) as caught:
                        self._read()
                    self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
            finally:
                setattr(self.repository, field, original)

    def test_removed_member_and_invalid_input_do_not_read_source(self):
        self.project.role = None
        with self.assertRaises(DocumentReadError) as caught:
            self._read()
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repository.calls, [])
        with self.assertRaises(DocumentReadError) as caught:
            self.service.get_source_facts_for_evidence(
                self.tx, self.query, self.document_id, uuid.UUID(int=0))
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
