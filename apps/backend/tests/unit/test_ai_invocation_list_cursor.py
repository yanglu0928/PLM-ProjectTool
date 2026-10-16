from __future__ import annotations

import uuid
from dataclasses import replace
from unittest import TestCase

from plm_assistant.modules.ai.api.invocation_list_cursor import (
    AIInvocationListCursorCodec,
)
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.invocation_read import (
    AIInvocationReadError,
    ListAIInvocations,
)
from plm_assistant.modules.ai.application.task_read import ListAITasks


class AIInvocationListCursorTests(TestCase):
    def setUp(self) -> None:
        self.query = ListAIInvocations(
            b"s" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 50,
        )
        self.position = (3, uuid.uuid4())
        self.codec = AIInvocationListCursorCodec(b"c" * 32)

    def test_round_trip_and_all_bindings(self):
        token = self.codec.encode(query=self.query, before=self.position)
        self.assertEqual(self.codec.decode(token, query=self.query), self.position)
        self.assertNotIn(str(self.query.ai_task_id), token)
        self.assertNotIn(str(self.position[1]), token)
        for query in (
            replace(self.query, session_token=b"x" * 32),
            replace(self.query, project_id=uuid.uuid4()),
            replace(self.query, ai_task_id=uuid.uuid4()),
            replace(self.query, page_size=51),
        ):
            with self.subTest(query=query), self.assertRaises(AIInvocationReadError):
                self.codec.decode(token, query=query)

    def test_same_key_cannot_cross_task_and_invocation_families(self):
        token = self.codec.encode(query=self.query, before=self.position)
        task_query = ListAITasks(
            self.query.session_token, self.query.trace_id, self.query.project_id, 50,
        )
        with self.assertRaises(Exception):
            AITaskListCursorCodec(b"c" * 32).decode(token, query=task_query)


if __name__ == "__main__":
    import unittest
    unittest.main()
