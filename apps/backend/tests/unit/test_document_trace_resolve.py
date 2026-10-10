from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadService, DocumentTraceIdentity,
    DocumentVersionView,
)


class _Repository:
    def __init__(self) -> None:
        self.identity = None
        self.calls = []

    def get_trace_identity(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.identity


class _Guard:
    def __init__(self) -> None:
        self.calls = 0

    def require_valid(self, *, trace_id):
        self.calls += 1


class DocumentTraceResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tx = object()
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()
        self.version = uuid.uuid4()
        self.repo = _Repository()
        self.guard = _Guard()
        self.service = DocumentReadService(
            unit_of_work=lambda: None, session_access=object(),
            admin_access=object(), project_facts=object(),
            license_guard=self.guard, repository=self.repo,
        )
        self.proof_queries = []

        def prove(tx, query, document_id, version_id):
            self.proof_queries.append((tx, query, document_id, version_id))
            return DocumentVersionView(
                version_id, document_id, 1, "a" * 64, 1,
                "application/pdf", "AVAILABLE", None,
                datetime.now(timezone.utc), None,
            )

        self.service.get_version_for_trace = prove

    def _resolve(self):
        return self.service.resolve_version_for_trace(
            self.tx, session_token=b"s" * 32, trace_id=uuid.uuid4(),
            path_project_id=self.project, document_id=self.document,
            document_version_id=self.version,
        )

    def test_project_identity_is_proved_in_same_transaction(self) -> None:
        self.repo.identity = DocumentTraceIdentity(
            self.document, self.version, "PROJECT", self.project,
        )
        self.assertEqual(self._resolve(), self.repo.identity)
        self.assertIs(self.repo.calls[0][0], self.tx)
        self.assertIs(self.proof_queries[0][0], self.tx)
        self.assertEqual((self.proof_queries[0][1].scope,
                          self.proof_queries[0][1].project_id),
                         ("PROJECT", self.project))

    def test_global_identity_requires_global_owner_proof(self) -> None:
        self.repo.identity = DocumentTraceIdentity(
            self.document, self.version, "GLOBAL", None,
        )
        self.assertEqual(self._resolve(), self.repo.identity)
        self.assertEqual((self.proof_queries[0][1].scope,
                          self.proof_queries[0][1].project_id),
                         ("GLOBAL", None))

    def test_cross_project_missing_and_forged_identity_fail_before_proof(self) -> None:
        for identity in (
            None,
            DocumentTraceIdentity(self.document, self.version, "PROJECT", uuid.uuid4()),
            DocumentTraceIdentity(self.document, uuid.uuid4(), "PROJECT", self.project),
        ):
            self.repo.identity = identity
            with self.subTest(identity=identity), self.assertRaises(DocumentReadError) as caught:
                self._resolve()
            self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.proof_queries, [])

    def test_invalid_input_is_rejected_before_lookup(self) -> None:
        with self.assertRaises(DocumentReadError):
            self.service.resolve_version_for_trace(
                self.tx, session_token=b"short", trace_id=uuid.uuid4(),
                path_project_id=self.project, document_id=self.document,
                document_version_id=self.version,
            )
        self.assertEqual(self.repo.calls, [])
        self.assertEqual(self.guard.calls, 0)


if __name__ == "__main__":
    unittest.main()
