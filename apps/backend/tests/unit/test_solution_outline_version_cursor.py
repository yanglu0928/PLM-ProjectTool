from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.outline_version_list_cursor import (
    OutlineVersionListCursorCodec,
)


class OutlineVersionCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = OutlineVersionListCursorCodec(b"c" * 32)
        self.project, self.outline = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32
        self.cursor = self.codec.encode(
            session_token=self.session, project_id=self.project,
            outline_id=self.outline, page_size=1, before_version_no=2)

    def test_roundtrip_and_query_identity(self):
        self.assertEqual(self.codec.decode(
            self.cursor, session_token=self.session,
            project_id=self.project, outline_id=self.outline,
            page_size=1), 2)
        self.assertNotIn(str(self.session.hex()), self.cursor)
        for values in (
            {"session_token": b"x" * 32},
            {"project_id": uuid.uuid4()},
            {"outline_id": uuid.uuid4()},
            {"page_size": 2},
        ):
            with self.subTest(values=values), self.assertRaises(ApplicationError) as caught:
                self.codec.decode(self.cursor, **{
                    "session_token": self.session, "project_id": self.project,
                    "outline_id": self.outline, "page_size": 1, **values})
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_tamper_wrong_family_and_invalid_position_fail_closed(self):
        for value in (self.cursor[:-1] + ("A" if self.cursor[-1] != "A" else "B"),
                      "abc.def", "", self.cursor + "x"):
            with self.subTest(value=value), self.assertRaises(ApplicationError):
                self.codec.decode(value, session_token=self.session,
                                  project_id=self.project,
                                  outline_id=self.outline, page_size=1)
        for position in (0, 1, True):
            with self.subTest(position=position), self.assertRaises(ValueError):
                self.codec.encode(session_token=self.session,
                                  project_id=self.project,
                                  outline_id=self.outline, page_size=1,
                                  before_version_no=position)
        with self.assertRaises(ValueError):
            OutlineVersionListCursorCodec(b"short")
