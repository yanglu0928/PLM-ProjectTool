from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


class MemberListCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = MemberListCursorCodec(b"k" * 32)
        self.session = b"s" * 32
        self.project_id = uuid.uuid4()
        self.member_id = uuid.uuid4()
        self.token = self.codec.encode(
            session_token=self.session, project_id=self.project_id,
            page_size=2, member_id=self.member_id,
        )

    def test_roundtrip_and_scope_binding(self):
        self.assertEqual(self.codec.decode(
            self.token, session_token=self.session,
            project_id=self.project_id, page_size=2,
        ), self.member_id)
        for kwargs in (
            {"session_token": b"o" * 32, "project_id": self.project_id, "page_size": 2},
            {"session_token": self.session, "project_id": uuid.uuid4(), "page_size": 2},
            {"session_token": self.session, "project_id": self.project_id, "page_size": 3},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ApplicationError) as caught:
                self.codec.decode(self.token, **kwargs)
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_tamper_other_key_and_malformed_rejected(self):
        for token, codec in (
            (self.token[:-1] + ("A" if self.token[-1] != "A" else "B"), self.codec),
            (self.token, MemberListCursorCodec(b"x" * 32)),
            ("not-a-cursor", self.codec),
        ):
            with self.subTest(token=token[:12]), self.assertRaises(ApplicationError) as caught:
                codec.decode(token, session_token=self.session,
                             project_id=self.project_id, page_size=2)
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_invalid_key_and_positions_rejected(self):
        with self.assertRaises(ValueError):
            MemberListCursorCodec(b"short")
        with self.assertRaises(ValueError):
            self.codec.encode(session_token=self.session, project_id=self.project_id,
                              page_size=201, member_id=self.member_id)
        with self.assertRaises(ValueError):
            self.codec.encode(session_token=self.session, project_id=self.project_id,
                              page_size=2, member_id=uuid.UUID(int=0))


if __name__ == "__main__":
    unittest.main()
