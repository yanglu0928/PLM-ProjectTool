from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec


class SectionCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = SectionListCursorCodec(b"s" * 32)
        self.session = b"a" * 32
        self.project = uuid.uuid4()
        self.section = uuid.uuid4()

    def token(self):
        return self.codec.encode(session_token=self.session,
                                 project_id=self.project, page_size=2,
                                 section_id=self.section)

    def decode(self, token, **overrides):
        params = dict(session_token=self.session, project_id=self.project, page_size=2)
        params.update(overrides)
        return self.codec.decode(token, **params)

    def reject(self, token, **overrides):
        with self.assertRaises(ApplicationError) as caught:
            self.decode(token, **overrides)
        self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_round_trip_and_boundary(self):
        self.assertEqual(self.decode(self.token()), self.section)
        with self.assertRaises(ValueError):
            SectionListCursorCodec(b"short")
        with self.assertRaises(ValueError):
            self.codec.encode(session_token=self.session, project_id=self.project,
                              page_size=0, section_id=self.section)

    def test_scope_binding_and_tamper(self):
        token = self.token()
        self.reject(token, session_token=b"b" * 32)
        self.reject(token, project_id=uuid.uuid4())
        self.reject(token, page_size=3)
        self.reject(token[:-1] + ("A" if token[-1] != "A" else "B"))
        self.reject("invalid")
        other = SectionListCursorCodec(b"t" * 32)
        with self.assertRaises(ApplicationError):
            other.decode(token, session_token=self.session,
                         project_id=self.project, page_size=2)

    def test_outline_family_cannot_cross_even_with_same_key(self):
        outline = OutlineListCursorCodec(b"s" * 32)
        outline_token = outline.encode(
            session_token=self.session, project_id=self.project,
            page_size=2, outline_id=self.section)
        self.reject(outline_token)
        with self.assertRaises(ApplicationError):
            outline.decode(self.token(), session_token=self.session,
                           project_id=self.project, page_size=2)


if __name__ == "__main__":
    unittest.main()
