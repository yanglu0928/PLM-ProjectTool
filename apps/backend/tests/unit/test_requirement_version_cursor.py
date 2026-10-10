from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.requirement.api.version_cursor import (
    RequirementVersionCursorCodec,
)


class RequirementVersionCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = RequirementVersionCursorCodec(b"v" * 32)
        self.project, self.requirement = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32

    def token(self):
        return self.codec.encode(
            project_id=self.project, requirement_id=self.requirement,
            session_token=self.session, page_size=25, version_no=7)

    def test_round_trip_version_number(self):
        self.assertEqual(7, self.codec.decode(
            self.token(), project_id=self.project,
            requirement_id=self.requirement,
            session_token=self.session, page_size=25))

    def test_parent_session_query_and_signature_are_bound(self):
        token = self.token()
        for project, requirement, session, size, candidate in (
            (uuid.uuid4(), self.requirement, self.session, 25, token),
            (self.project, uuid.uuid4(), self.session, 25, token),
            (self.project, self.requirement, b"x" * 32, 25, token),
            (self.project, self.requirement, self.session, 24, token),
            (self.project, self.requirement, self.session, 25,
             token[:-1] + ("A" if token[-1] != "A" else "B")),
        ):
            with self.subTest(size=size), self.assertRaises(ApplicationError) as caught:
                self.codec.decode(
                    candidate, project_id=project, requirement_id=requirement,
                    session_token=session, page_size=size)
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")

    def test_dedicated_key_and_position_are_strict(self):
        for key in (b"short", bytearray(b"v" * 32)):
            with self.assertRaises(ValueError):
                RequirementVersionCursorCodec(key)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.codec.encode(
                project_id=self.project, requirement_id=self.requirement,
                session_token=self.session, page_size=25, version_no=0)


if __name__ == "__main__":
    unittest.main()
