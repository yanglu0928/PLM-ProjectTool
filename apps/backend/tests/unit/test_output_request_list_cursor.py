from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError


class OutputRequestListCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = OutputRequestListCursorCodec(bytes.fromhex("7a" * 32))
        self.token, self.project_id = bytes.fromhex("33" * 32), uuid.uuid4()
        self.request_id = uuid.uuid4()
        self.at = datetime(2026, 11, 4, 8, 15, 30, 123456, tzinfo=timezone.utc)

    def test_signed_cursor_round_trips_full_query_scope(self):
        encoded = self.codec.encode(
            session_token=self.token, project_id=self.project_id, page_size=25,
            requested_at=self.at, request_id=self.request_id,
        )
        self.assertEqual(self.codec.decode(
            encoded, session_token=self.token, project_id=self.project_id,
            page_size=25,
        ), (self.at, self.request_id))

    def test_tampering_and_cross_scope_replay_fail_closed(self):
        encoded = self.codec.encode(
            session_token=self.token, project_id=self.project_id, page_size=25,
            requested_at=self.at, request_id=self.request_id,
        )
        other_project, other_session = uuid.uuid4(), bytes.fromhex("44" * 32)
        for kwargs in (
            {"session_token": self.token, "project_id": other_project, "page_size": 25},
            {"session_token": other_session, "project_id": self.project_id, "page_size": 25},
            {"session_token": self.token, "project_id": self.project_id, "page_size": 26},
        ):
            with self.assertRaises(ApplicationError):
                self.codec.decode(encoded, **kwargs)
        head, tail = encoded.split(".")
        tampered = ("A" if head[0] != "A" else "B") + head[1:] + "." + tail
        with self.assertRaises(ApplicationError):
            self.codec.decode(tampered, session_token=self.token,
                              project_id=self.project_id, page_size=25)

    def test_wrong_key_length_is_rejected(self):
        with self.assertRaises(ValueError):
            OutputRequestListCursorCodec(b"short")


if __name__ == "__main__":
    unittest.main()
