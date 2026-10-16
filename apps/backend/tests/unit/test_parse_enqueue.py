from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseEnqueueError, ParseJobQueue, ParseJobRequest,
)


class _Spy:
    def __init__(self) -> None:
        self.calls = 0

    def enqueue_parse(self, transaction, *, request):
        self.calls += 1
        return object()


class ParseJobQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spy = _Spy()
        self.queue = ParseJobQueue(self.spy)
        self.request = ParseJobRequest(
            upload_id=uuid.uuid4(), document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(), version_no=1,
            scope="GLOBAL", project_id=None,
            actor_id=uuid.uuid4(), trace_id=uuid.uuid4(),
        )

    def test_accepts_valid_request_without_committing(self) -> None:
        self.queue.enqueue_parse(object(), request=self.request)
        self.assertEqual(self.spy.calls, 1)

    def test_rejects_invalid_scope_and_version(self) -> None:
        from dataclasses import replace
        for request in (
            replace(self.request, version_no=0),
            replace(self.request, scope="PROJECT"),
            replace(self.request, scope="GLOBAL", project_id=uuid.uuid4()),
            replace(self.request, upload_id=uuid.UUID(int=0)),
        ):
            with self.subTest(request=request), self.assertRaises(ParseEnqueueError):
                self.queue.enqueue_parse(object(), request=request)
        self.assertEqual(self.spy.calls, 0)


if __name__ == "__main__":
    unittest.main()
