from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadQuery, DocumentReadService,
)


class DocumentReadValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "GLOBAL", None)

    def test_invalid_scope_session_or_trace_rejected(self) -> None:
        for query in (
            replace(self.query, session_token=b"short"),
            replace(self.query, trace_id=uuid.UUID(int=0)),
            replace(self.query, scope="PROJECT"),
            replace(self.query, scope="GLOBAL", project_id=uuid.uuid4()),
        ):
            with self.subTest(query=query), self.assertRaises(DocumentReadError):
                DocumentReadService._validate_query(query)

    def test_invalid_version_identity_and_page_size_rejected(self) -> None:
        class Guard:
            def require_valid(self, *, trace_id):
                raise AssertionError("invalid request reached License Guard")

        service = DocumentReadService(
            unit_of_work=lambda: object(), session_access=object(),
            admin_access=object(), project_facts=object(), license_guard=Guard(),
            repository=object(),
        )
        for document_id, before, limit in (
            (uuid.UUID(int=0), None, 50),
            (uuid.uuid4(), 0, 50),
            (uuid.uuid4(), True, 50),
            (uuid.uuid4(), None, 201),
        ):
            with self.subTest(before=before, limit=limit), self.assertRaises(DocumentReadError):
                service.list_versions(self.query, document_id,
                                      before_version_no=before, limit=limit)
        with self.assertRaises(DocumentReadError):
            service.get_version(self.query, uuid.uuid4(), uuid.UUID(int=0))


if __name__ == "__main__":
    unittest.main()
