from __future__ import annotations

import unittest
import inspect
from unittest.mock import Mock

from sqlalchemy import create_engine

from plm_assistant.entrypoints.windows_rag_retrieval import (
    RAG_RETRIEVAL_QUERY_KEY_REF,
    WindowsRAGRetrievalStartupError,
    create_windows_rag_retrieval_api,
    create_windows_rag_retrieval_worker,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.rag.application.retrieval_cancel import (
    RAGRetrievalCancelOwner,
    RAGRetrievalCancelReconciler,
)
from plm_assistant.modules.rag.application.retrieval_worker import (
    RAGRetrievalOneShotWorker,
)


class _Keys:
    def __init__(self, value):
        self.value, self.refs = value, []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        return self.value


class WindowsRAGRetrievalCompositionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = DatabaseRuntime(create_engine("sqlite+pysqlite:///:memory:"))
        self.addCleanup(self.runtime.dispose)
        self.guard = Mock()
        self.actor = Mock()

    def test_api_uses_one_owner_and_dedicated_key(self):
        keys = _Keys(b"r" * 32)
        composition = create_windows_rag_retrieval_api(
            self.runtime, sessions=Mock(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            license_guard=self.guard, key_resolver=keys,
        )
        self.assertIsInstance(
            composition.cancellation_owner, RAGRetrievalCancelOwner,
        )
        self.assertIs(
            inspect.getclosurevars(
                composition.cancel_router.routes[0].endpoint,
            ).nonlocals["cancellations"],
            composition.cancellation_owner,
        )
        paths = {route.path for route in composition.router.routes}
        self.assertIn(
            "/api/v1/projects/{project_id}/retrieval-runs", paths,
        )
        self.assertEqual(keys.refs, [RAG_RETRIEVAL_QUERY_KEY_REF])

    def test_worker_is_local_and_missing_key_fails_closed(self):
        keys = _Keys(b"r" * 32)
        composition = create_windows_rag_retrieval_worker(
            self.runtime, license_guard=self.guard,
            system_actor=self.actor, key_resolver=keys,
        )
        self.assertIsInstance(composition.worker, RAGRetrievalOneShotWorker)
        self.assertIsInstance(
            composition.cancel_reconciler, RAGRetrievalCancelReconciler,
        )
        self.assertEqual(keys.refs, [RAG_RETRIEVAL_QUERY_KEY_REF])
        for value in (None, b"short", "not-bytes"):
            with self.subTest(value=value), self.assertRaises(
                WindowsRAGRetrievalStartupError,
            ):
                create_windows_rag_retrieval_worker(
                    self.runtime, license_guard=self.guard,
                    system_actor=self.actor, key_resolver=_Keys(value),
                )


if __name__ == "__main__":
    unittest.main()
