from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.handover.api.action_list_cursor import HandoverActionListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError


class HandoverActionListCursorTests(unittest.TestCase):
    def test_round_trip_and_context_binding(self):
        codec = HandoverActionListCursorCodec(b"k" * 32)
        session, project = b"s" * 32, uuid.uuid4()
        position = (datetime(2026, 10, 5, 12, 0, 1, 123456,
                             tzinfo=timezone.utc), uuid.uuid4())
        token = codec.encode(
            session_token=session, project_id=project, page_size=50,
            updated_at=position[0], action_item_id=position[1],
        )
        self.assertEqual(position, codec.decode(
            token, session_token=session, project_id=project, page_size=50,
        ))
        for values in (
            {"session_token": b"x" * 32, "project_id": project, "page_size": 50},
            {"session_token": session, "project_id": uuid.uuid4(), "page_size": 50},
            {"session_token": session, "project_id": project, "page_size": 51},
        ):
            with self.subTest(values=values), self.assertRaises(ApplicationError):
                codec.decode(token, **values)

    def test_tamper_and_wrong_key_fail_closed(self):
        codec = HandoverActionListCursorCodec(b"k" * 32)
        values = dict(
            session_token=b"s" * 32, project_id=uuid.uuid4(), page_size=2,
            updated_at=datetime.now(timezone.utc), action_item_id=uuid.uuid4(),
        )
        token = codec.encode(**values)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        for candidate, reader in (
            (tampered, codec), (token, HandoverActionListCursorCodec(b"z" * 32)),
        ):
            with self.assertRaises(ApplicationError):
                reader.decode(candidate, session_token=values["session_token"],
                              project_id=values["project_id"], page_size=2)

    def test_requires_dedicated_key(self):
        with self.assertRaises(ValueError):
            HandoverActionListCursorCodec(b"short")


if __name__ == "__main__":
    unittest.main()
