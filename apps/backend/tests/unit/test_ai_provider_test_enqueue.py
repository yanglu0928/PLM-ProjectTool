from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import (
    AIProviderTestEnqueueError, AIProviderTestJobQueue, AIProviderTestJobRef,
    AIProviderTestJobRequest,
)


class AIProviderTestEnqueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = AIProviderTestJobRequest(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1, uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), b"p" * 32,
        )

    def test_request_and_ref_are_strict(self) -> None:
        for change in (
            {"submission_id": uuid.UUID(int=0)}, {"provider_id": "bad"},
            {"config_version": 0}, {"config_version": True},
            {"policy_sha256": b"short"}, {"probe_id": "CUSTOM_PROMPT"},
        ):
            with self.subTest(change=change), self.assertRaises(AIProviderTestEnqueueError):
                replace(self.request, **change)
        with self.assertRaises(AIProviderTestEnqueueError):
            AIProviderTestJobRef(uuid.uuid4(), uuid.UUID(int=0))

    def test_queue_preserves_repository_result_and_rejects_bad_result(self) -> None:
        ref = AIProviderTestJobRef(uuid.uuid4(), uuid.uuid4())
        repo = Mock(enqueue=Mock(return_value=ref), find=Mock(return_value=ref))
        queue = AIProviderTestJobQueue(repo)
        self.assertEqual(queue.enqueue(object(), request=self.request), ref)
        self.assertEqual(queue.find(object(), request=self.request), ref)
        repo.find.return_value = None
        self.assertIsNone(queue.find(object(), request=self.request))
        repo.enqueue.return_value = None
        with self.assertRaises(AIProviderTestEnqueueError):
            queue.enqueue(object(), request=self.request)

    def test_queue_never_accepts_untyped_request_or_missing_repository(self) -> None:
        with self.assertRaises(ValueError):
            AIProviderTestJobQueue(None)  # type: ignore[arg-type]
        queue = AIProviderTestJobQueue(Mock())
        with self.assertRaises(AIProviderTestEnqueueError):
            queue.enqueue(object(), request=object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
