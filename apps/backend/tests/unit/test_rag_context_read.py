from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentReadQuery,
    AIExecutionContextIdentity,
)
from plm_assistant.modules.ai.infrastructure.rag_context_owner import (
    AIRAGContextReadOwner,
)
from plm_assistant.modules.rag.application.retrieval_context import (
    RAGContextProjection,
    RAGContextReadError,
    RAGContextReadRequest,
    RAGContextReadService,
)


class _Authorization:
    def __init__(self): self.calls = 0
    def require_in_transaction(self, *_args, **_kwargs):
        self.calls += 1
        return object()


class _Guard:
    def __init__(self): self.calls = 0
    def require_valid(self, **_kwargs): self.calls += 1


class _Repository:
    def __init__(self, projection): self.projection = projection
    def read_exact(self, _transaction, *, request): return self.projection


class RAGContextReadTests(unittest.TestCase):
    def setUp(self):
        self.project, self.actor, self.trace, self.run, self.bundle = (
            uuid.uuid4() for _ in range(5))
        self.body = b'{"schema_version":"rag-context-minimum-text.v1"}'
        self.projection = RAGContextProjection(
            self.run, self.bundle, b"f" * 32, 1, self.body,
        )
        self.auth, self.guard = _Authorization(), _Guard()
        self.service = RAGContextReadService(
            authorization=self.auth, license_guard=self.guard,
            repository=_Repository(self.projection),
        )

    def request(self, *, size=None):
        return RAGContextReadRequest(
            self.project, self.actor, self.trace, self.run, self.bundle,
            b"f" * 32, 1, len(self.body) if size is None else size,
        )

    def test_service_rechecks_authorization_license_and_exact_size(self):
        result = self.service.read_exact(object(), request=self.request())
        self.assertEqual(result.content_utf8, self.body)
        self.assertEqual(self.auth.calls, 1)
        self.assertEqual(self.guard.calls, 2)
        with self.assertRaises(RAGContextReadError):
            self.service.read_exact(object(), request=self.request(size=99))

    def test_ai_adapter_only_accepts_complete_rag_identity(self):
        owner = AIRAGContextReadOwner(self.service)
        query = AIExecutionContentReadQuery(
            uuid.uuid4(), uuid.uuid4(), self.project, uuid.uuid4(),
            self.actor, self.trace, uuid.uuid4(), "gap.analysis.v1",
            "minimum.document.text.v1",
        )
        context = AIExecutionContextIdentity(
            "project-documents.v1", "RAG_CONTEXT", self.run, self.bundle,
            b"f" * 32, 1, len(self.body),
        )
        self.assertEqual(owner.read_exact(object(), query, context), self.body.decode())
        with self.assertRaises(RuntimeError):
            owner.read_exact(
                object(), query,
                AIExecutionContextIdentity("no-retrieval.v1", "NONE"),
            )


if __name__ == "__main__":
    unittest.main()
