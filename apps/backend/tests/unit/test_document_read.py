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


if __name__ == "__main__":
    unittest.main()
