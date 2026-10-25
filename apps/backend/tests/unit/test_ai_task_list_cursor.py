from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase

from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.task_read import AITaskReadError, ListAITasks


class AITaskListCursorTests(TestCase):
    def setUp(self) -> None:
        self.query = ListAITasks(
            b"s" * 32, uuid.uuid4(), uuid.uuid4(), 50,
        )
        self.position = (
            datetime(2026, 10, 3, 10, 2, 3, 123456, tzinfo=timezone.utc),
            uuid.uuid4(),
        )
        self.codec = AITaskListCursorCodec(b"c" * 32)

    def test_round_trip_is_opaque_and_bound_to_request(self):
        token = self.codec.encode(query=self.query, before=self.position)
        self.assertEqual(self.codec.decode(token, query=self.query), self.position)
        self.assertNotIn(str(self.query.project_id), token)
        self.assertNotIn(str(self.position[1]), token)
        for changed in (
            replace(self.query, session_token=b"x" * 32),
            replace(self.query, project_id=uuid.uuid4()),
            replace(self.query, page_size=51),
        ):
            with self.subTest(changed=changed), self.assertRaises(AITaskReadError):
                self.codec.decode(token, query=changed)

    def test_tamper_wrong_key_and_malformed_tokens_fail_closed(self):
        token = self.codec.encode(query=self.query, before=self.position)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        for codec, value in (
            (self.codec, tampered),
            (AITaskListCursorCodec(b"d" * 32), token),
            (self.codec, "ait1.not-base64!"),
        ):
            with self.subTest(value=value), self.assertRaises(AITaskReadError) as caught:
                codec.decode(value, query=self.query)
            self.assertEqual(caught.exception.code, "REQUEST_MALFORMED")


if __name__ == "__main__":
    import unittest
    unittest.main()
