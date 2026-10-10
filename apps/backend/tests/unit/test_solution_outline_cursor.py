"""Independent Outline cursor is bound to current Session and query."""

from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec


class OutlineCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = OutlineListCursorCodec(b"o" * 32)
        self.project, self.outline = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32
        self.token = self.codec.encode(
            session_token=self.session, project_id=self.project,
            page_size=25, outline_id=self.outline)

    def test_roundtrip_and_context_binding(self):
        self.assertEqual(self.outline, self.codec.decode(
            self.token, session_token=self.session,
            project_id=self.project, page_size=25))
        variants = (
            (self.token, b"t" * 32, self.project, 25),
            (self.token, self.session, uuid.uuid4(), 25),
            (self.token, self.session, self.project, 50),
            (self.token[:-1] + ("A" if self.token[-1] != "A" else "B"),
             self.session, self.project, 25),
            ("not-a-cursor", self.session, self.project, 25),
        )
        for token, session, project, size in variants:
            with self.subTest(token=token), self.assertRaises(ApplicationError) as caught:
                self.codec.decode(token, session_token=session,
                                  project_id=project, page_size=size)
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_other_family_or_key_cannot_decode(self):
        reference = ReferenceListCursorCodec(b"o" * 32).encode(
            session_token=self.session, project_id=self.project,
            page_size=25, reference_solution_id=self.outline)
        for codec, token in (
            (self.codec, reference),
            (OutlineListCursorCodec(b"x" * 32), self.token),
        ):
            with self.subTest(token=token), self.assertRaises(ApplicationError):
                codec.decode(token, session_token=self.session,
                             project_id=self.project, page_size=25)

    def test_rejects_invalid_key_and_positions(self):
        for bad in (b"short", bytearray(b"o" * 32)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                OutlineListCursorCodec(bad)
        for bad in (0, 101, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.codec.encode(session_token=self.session,
                                  project_id=self.project,
                                  page_size=bad, outline_id=self.outline)
        with self.assertRaises(ValueError):
            self.codec.encode(session_token=self.session,
                              project_id=self.project,
                              page_size=25, outline_id=uuid.UUID(int=0))


if __name__ == "__main__":
    unittest.main()
